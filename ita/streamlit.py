
import requests
import streamlit as st

st.set_page_config(
    page_title="Idea Triage Agent",
    layout="wide",
)

st.title("Idea Triage Agent")
st.caption("Submit ideas, track progress, and review approvals.")


# SESSION STATE

DEFAULTS = {
    "selected_role": "User",
    "last_user_id": "",
    "last_reviewer_id": "",
    "active_task_id": None,
    "active_thread_id": None,
    "active_idea": None,
    "active_idea_owner": None,
    "user_ideas": [],
    "pending_approvals": [],
    "escalated_approvals": [],
}

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


# API CONFIGURATION

st.sidebar.header("API Configuration")

api_url = (
    st.sidebar.text_input(
        "FastAPI base URL",
        value="http://127.0.0.1:8000",
    )
    .strip()
    .rstrip("/")
)


# API HELPER

def api_request(method, endpoint, params=None, json_body=None):
    """Streamlit communicates with FastAPI, never directly with SQL."""

    try:
        response = requests.request(
            method=method,
            url=f"{api_url}{endpoint}",
            params=params,
            json=json_body,
            timeout=120,
        )

    except requests.exceptions.Timeout:
        st.error(
            "The API request timed out. Refresh the idea status "
            "before retrying."
        )
        return None

    except requests.exceptions.ConnectionError:
        st.error(
            "Could not connect to FastAPI. Start Uvicorn and "
            "check the API URL."
        )
        return None

    except requests.exceptions.RequestException as exc:
        st.error(f"The request could not be completed: {exc}")
        return None

    try:
        result = response.json()
    except ValueError:
        result = {}

    if not response.ok:
        detail = result.get("detail") if isinstance(result, dict) else None

        if response.status_code in (400, 401, 403, 404, 409, 422):
            st.error(
                detail if isinstance(detail, str)
                else f"API request failed with HTTP {response.status_code}."
            )
        else:
            st.error(
                "The API could not complete the request. "
                "Check the FastAPI server logs before retrying."
            )

        return None

    if not isinstance(result, dict):
        st.error("The API returned an unexpected response format.")
        return None

    return result


# GENERAL HELPERS

def get_task_id(item):
    """There is one Task ID per submitted-draft cycle."""
    value = item.get("task_id")
    return str(value) if value else None


def status_label(item):
    return str(
        item.get("status")
        or item.get("approval_status")
        or item.get("run_status")
        or "UNKNOWN"
    ).replace("_", " ").title()


def idea_reference(item):
    """
    Use Task ID when a draft has been submitted.
    Otherwise use thread_id to reopen an idea awaiting its first draft.
    """
    return get_task_id(item) or item.get("thread_id")


def idea_label(item):
    """Show a friendly label without exposing internal IDs."""
    task_id = get_task_id(item)

    if task_id:
        return f"Task: {task_id} | {status_label(item)}"
    return f"Draft not submitted | {status_label(item)}"


def get_interrupt_type(idea):
    values = []

    for key in ("interrupt_type", "interrupt", "interrupt_payload"):
        value = idea.get(key)

        if isinstance(value, str):
            values.append(value)

        elif isinstance(value, dict):
            for nested_key in (
                "type",
                "interrupt_type",
                "name",
                "message",
            ):
                nested = value.get(nested_key)
                if isinstance(nested, str):
                    values.append(nested)

            nested_payload = value.get("value")
            if isinstance(nested_payload, dict):
                for nested_key in (
                    "type",
                    "interrupt_type",
                    "name",
                    "message",
                ):
                    nested = nested_payload.get(nested_key)
                    if isinstance(nested, str):
                        values.append(nested)

        elif isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    for nested_key in (
                        "type",
                        "interrupt_type",
                        "name",
                        "message",
                    ):
                        nested = entry.get(nested_key)
                        if isinstance(nested, str):
                            values.append(nested)

    return " ".join(values).lower()


def draft_summary_is_required(idea):
    if idea.get("needs_draft_summary") is True:
        return True

    status = str(idea.get("status") or "").strip().lower()
    current_node = str(idea.get("current_node") or "").strip().lower()
    interrupt_type = get_interrupt_type(idea)

    draft_statuses = {
        "draft_summary_required",
        "awaiting_draft_summary",
        "draft_summary_pending",
        "draft_required",
        "awaiting_draft_summary",
    }

    draft_nodes = {
        "draft summary",
        "draft_summary",
        "draft_summary_node",
        "draftsummary",
    }

    if status in draft_statuses or current_node in draft_nodes:
        return True

    if "draft_summary" in interrupt_type or "draft summary" in interrupt_type:
        return True

    return False


def approval_is_required(idea):
    # Trust the explicit checkpoint-derived API field.
    if "needs_approval" in idea:
        return idea.get("needs_approval") is True

    interrupt_type = get_interrupt_type(idea)
    return (
        "approval" in interrupt_type
        and "draft" not in interrupt_type
    )


def render_classification(classification):
    """Display the idea category in a readable format."""
    st.markdown("**Classification**")

    if isinstance(classification, dict):
        category = classification.get("category")

        if category:
            st.write(f"**Category:** {category}")
        else:
            st.write("Classification is available, but no category was returned.")
    elif isinstance(classification, str):
        st.write(f"**Category:** {classification}")
    else:
        st.write("Classification is not available.")


def render_idea_assessment(assessment):
    """Display the idea score, individual scores, and explanation."""
    st.markdown("**Idea assessment**")

    if not isinstance(assessment, dict):
        st.write("Assessment is not available.")
        return

    idea_score = assessment.get("idea_score")

    if idea_score is not None:
        st.metric("Overall quality score", f"{float(idea_score):.0%}")

    scores = assessment.get("scores") or {}

    score_labels = {
        "clarity": "Clarity",
        "impact": "Impact",
        "feasibility": "Feasibility",
        "specificity": "Specificity",
    }

    if isinstance(scores, dict) and scores:
        st.markdown("**Evaluation criteria**")

        for key, label in score_labels.items():
            value = scores.get(key)

            if value is not None:
                score = float(value)
                st.write(f"**{label}:** {score:.0%}")
                st.progress(max(0.0, min(1.0, score)))

    reason = assessment.get("reason")

    if reason:
        st.markdown("**Assessment explanation**")
        st.write(reason)


# LOAD / REFRESH AN IDEA

def load_one_idea(user_id, reference):
    """
    The reference may be a Task ID or, before the first draft,
    a thread ID.
    """
    result = api_request(
        "GET",
        f"/user/ideas/{reference}",
        params={"user_id": user_id},
    )

    if result is None:
        return

    task_id = get_task_id(result)
    thread_id = result.get("thread_id")

    st.session_state.active_task_id = task_id
    st.session_state.active_thread_id = (
        str(thread_id) if thread_id else None
    )
    st.session_state.active_idea = result
    st.session_state.active_idea_owner = user_id

    st.rerun()


# USER IDEA DISPLAY

def render_user_idea(user_id):
    idea = st.session_state.active_idea

    if not idea:
        return

    if st.session_state.active_idea_owner != user_id:
        return

    task_id = get_task_id(idea) or st.session_state.active_task_id
    thread_id = (
        idea.get("thread_id")
        or st.session_state.active_thread_id
    )

    st.divider()
    st.subheader("Selected idea")

    if task_id:
        st.caption("Current Task ID")
        st.code(str(task_id))
    else:
        st.info(
            "A Task ID will be generated when you submit "
            "your first draft summary."
        )

    status = str(idea.get("status") or "UNKNOWN").upper()

    submission = (
        idea.get("submission")
        or idea.get("idea")
        or idea.get("idea_text")
    )

    if submission:
        with st.expander("Submitted idea", expanded=True):
            st.write(submission)

    if idea.get("classification") is not None:
        render_classification(idea["classification"])

    if idea.get("idea_assessment") is not None:
        render_idea_assessment(idea["idea_assessment"])

    if (
        idea.get("duplicate_found") is True
        or "DUPLICATE" in status
    ):
        st.error("This idea appears to be a duplicate.")

        matches = idea.get("duplicate_matches") or []
        if matches:
            st.write("Potential matches")
            st.dataframe(
                matches,
                use_container_width=True,
                hide_index=True,
            )
        return

    decision = str(
        idea.get("reviewer_decision")
        or idea.get("approval_action")
        or ""
    ).upper()

    feedback = idea.get("reviewer_feedback")

    # Show the latest reviewer decision/comment.
    if decision in {"IMPROVE", "IMPROVED"} or (
        feedback and status in {"IMPROVE", "IMPROVED", "AWAITING_DRAFT_SUMMARY"}
    ):
        st.warning("The reviewer requested an improvement.")

        if feedback:
            st.markdown("**Reviewer comment**")
            st.write(feedback)

    elif decision in {"REJECT", "REJECTED"} or status == "REJECTED":
        st.error("Your idea has been rejected.")
        if feedback:
            st.markdown("**Reviewer comment**")
            st.write(feedback)

    elif decision in {"APPROVE", "APPROVED"} or status in {
        "APPROVED",
        "COMPLETED",
    }:
        st.success("Your idea has been approved.")

    # -----------------------------------------------------
    # STEP 1: DRAFT SUMMARY FORM
    # -----------------------------------------------------

    if draft_summary_is_required(idea):
        st.subheader("Draft summary")

        if decision in {"IMPROVE", "IMPROVED"} or feedback:
            st.info(
                "Review the feedback above and submit a revised draft summary."
            )
        else:
            st.info(
                "Your idea is saved. Submit a draft summary to begin review."
            )

        if not thread_id:
            st.error(
                "The workflow thread ID is missing from the API response. "
                "Refresh the idea or check the FastAPI logs."
            )
            return

        existing_summary = idea.get("draft_summary") or ""
        default_summary = "" if feedback else existing_summary

        # The form key changes for each cycle.
        form_reference = task_id or thread_id

        with st.form(
            f"draft_summary_form_{form_reference}",
            clear_on_submit=False,
        ):
            draft_summary = st.text_area(
                "Enter your draft summary",
                value=default_summary,
                height=200,
                placeholder=(
                    "1. Problem being addressed\n"
                    "2. Proposed solution\n"
                    "3. Expected benefits\n"
                    "4. Implementation considerations"
                ),
            )

            submit_summary = st.form_submit_button(
                "Submit draft summary",
                type="primary",
            )

        if submit_summary:
            if not draft_summary.strip():
                st.warning("Draft summary cannot be empty.")
                return

            body = {
                "user_id": user_id,
                "thread_id": str(thread_id),
                "draft_summary": draft_summary.strip(),
            }

            # Initial draft: no Task ID.
            # Revision: include the current Task ID.
            if task_id:
                body["task_id"] = str(task_id)

            result = api_request(
                "POST",
                "/user/draft-summary",
                json_body=body,
            )

            if result is not None:
                returned_task_id = get_task_id(result)

                if not returned_task_id:
                    st.error(
                        "The API did not return the new Task ID. "
                        "Refresh the idea status before retrying."
                    )
                    return

                updated_idea = {
                    **idea,
                    **result,
                }

                updated_idea["task_id"] = returned_task_id
                updated_idea["thread_id"] = str(thread_id)
                updated_idea["draft_summary"] = (
                    result.get("draft_summary")
                    or draft_summary.strip()
                )
                updated_idea["needs_draft_summary"] = (
                    result.get("needs_draft_summary", False)
                )
                updated_idea["needs_approval"] = (
                    result.get("needs_approval", False)
                )

                st.session_state.active_task_id = returned_task_id
                st.session_state.active_thread_id = str(thread_id)
                st.session_state.active_idea = updated_idea
                st.session_state.active_idea_owner = user_id

                st.success(
                    f"Draft submitted successfully. "
                    f"Your Task ID is {returned_task_id}."
                )
                st.rerun()

        return

    # -----------------------------------------------------
    # STEP 2: WAITING FOR REVIEWER
    # -----------------------------------------------------

    if approval_is_required(idea):
        st.info(
            "Your draft summary has been submitted. "
            "The workflow is waiting for a reviewer."
        )

        if idea.get("draft_summary"):
            st.markdown("**Submitted draft summary**")
            st.write(idea["draft_summary"])

        if st.button(
            "Refresh idea status",
            key=f"refresh_idea_{task_id or thread_id}",
        ):
            load_one_idea(user_id, task_id or thread_id)

        return

    # -----------------------------------------------------
    # STEP 3: TERMINAL OR OTHER STATUS
    # -----------------------------------------------------

    if status in {"APPROVED", "COMPLETED"} or decision in {
        "APPROVE",
        "APPROVED",
    }:
        st.success("Your idea has been approved or completed.")

    elif status == "REJECTED" or decision in {"REJECT", "REJECTED"}:
        st.error("Your idea has been rejected.")

    elif status == "ESCALATED":
        st.warning(
            "The approval has been escalated and requires reviewer action."
        )

    elif idea.get("is_complete"):
        st.success(f"Workflow finished. Status: {status_label(idea)}")

    else:
        st.info(f"Current workflow status: {status_label(idea)}")

    if st.button(
        "Refresh idea status",
        key=f"refresh_idea_{task_id or thread_id}",
    ):
        load_one_idea(user_id, task_id or thread_id)


# REVIEWER QUEUE

def render_classification(classification):
    st.markdown("**Classification**")

    if isinstance(classification, dict):
        category = classification.get("category")
        if category:
            st.write(f"**Category:** {category}")
        else:
            st.write("Classification details are unavailable.")
    elif isinstance(classification, str):
        st.write(f"**Category:** {classification}")
    else:
        st.write("Classification details are unavailable.")


def render_idea_assessment(assessment):
    st.markdown("**Idea Assessment**")

    if not isinstance(assessment, dict):
        st.write("Assessment details are unavailable.")
        return

    idea_score = assessment.get("idea_score")

    if idea_score is not None:
        try:
            score = float(idea_score)
            # Handle scores represented as either 0-1 or 0-100.
            if score > 1:
                score /= 100

            st.metric("Overall Quality Score", f"{score:.0%}")
        except (ValueError, TypeError):
            st.write(f"**Overall Quality Score:** {idea_score}")

    scores = assessment.get("scores") or {}

    labels = {
        "clarity": "Clarity",
        "impact": "Impact",
        "feasibility": "Feasibility",
        "specificity": "Specificity",
    }

    if isinstance(scores, dict) and scores:
        st.markdown("**Evaluation Criteria**")

        for key, label in labels.items():
            value = scores.get(key)

            if value is not None:
                try:
                    score = float(value)
                    if score > 1:
                        score /= 100

                    st.write(f"**{label}:** {score:.0%}")
                    st.progress(max(0.0, min(1.0, score)))
                except (ValueError, TypeError):
                    st.write(f"**{label}:** {value}")

    reason = assessment.get("reason")
    if reason:
        st.markdown("**Assessment Explanation**")
        st.write(reason)

def render_reviewer_queue(
    reviewer_id,
    queue_name,
    approvals,
    action_prefix,
):
    if not reviewer_id:
        st.info("Enter your Reviewer ID first.")
        return

    by_task = {
        str(item["task_id"]): item
        for item in approvals
        if item.get("task_id")
    }

    task_ids = list(by_task.keys())

    if not task_ids:
        st.info(
            f"No actionable {queue_name.lower()} are loaded. "
            f"Select Refresh {queue_name.lower()}."
        )
        return

    selected_task_id = st.selectbox(
        "Select a review task",
        options=task_ids,
        format_func=lambda value: (
            f"{value} | {status_label(by_task[value])}"
        ),
        key=f"{action_prefix}_selected_task",
    )

    selected = by_task[selected_task_id]

    st.markdown("### Idea details")

    st.caption("Task ID")
    st.code(selected_task_id)

    st.caption(f"Status: {status_label(selected)}")

    if selected.get("requested_at"):
        st.caption(f"Review requested at: {selected['requested_at']}")

    if selected.get("escalated_at"):
        st.caption(f"Escalated at: {selected['escalated_at']}")

    if selected.get("submission"):
        st.markdown("**Submitted idea**")
        st.write(selected["submission"])

    classification = selected.get("classification")
    if classification is not None:
      render_classification(classification)

# Idea quality assessment
    assessment = selected.get("idea_assessment")
    if assessment is not None:
      render_idea_assessment(assessment)

    if selected.get("draft_summary"):
        st.markdown("**Draft summary**")
        st.write(selected["draft_summary"])

    if selected.get("reviewer_feedback"):
        st.markdown("**Previous reviewer feedback**")
        st.write(selected["reviewer_feedback"])

    st.divider()

    action = st.selectbox(
        "Decision",
        options=["APPROVE", "REJECT", "IMPROVE"],
        format_func=lambda value: {
            "APPROVE": "Approve",
            "REJECT": "Reject",
            "IMPROVE": "Request improvement",
        }[value],
        key=f"{action_prefix}_action_{selected_task_id}",
    )

    comment = ""

    if action in {"IMPROVE", "REJECT"}:
        label = (
            "Improvement suggestions (required)"
            if action == "IMPROVE"
            else "Rejection reason"
        )

        comment = st.text_area(
            label,
            placeholder="Enter reviewer feedback...",
            key=f"{action_prefix}_comment_{selected_task_id}",
        )

    if st.button(
        "Submit decision",
        type="primary",
        key=f"{action_prefix}_submit_{selected_task_id}",
    ):
        if action == "IMPROVE" and not comment.strip():
            st.warning("A comment is required when requesting improvement.")
            return

        result = api_request(
            "POST",
            "/reviewer/decision",
            json_body={
                "task_id": selected_task_id,
                "reviewer_id": reviewer_id,
                "action": action,
                "comment": comment.strip(),
            },
        )

        if result is not None:
            st.success(result.get("message", "Decision submitted."))

            st.session_state.pending_approvals = [
                item
                for item in st.session_state.pending_approvals
                if str(item.get("task_id")) != selected_task_id
            ]

            st.session_state.escalated_approvals = [
                item
                for item in st.session_state.escalated_approvals
                if str(item.get("task_id")) != selected_task_id
            ]

            st.rerun()


# ROLE SELECTION

role = st.radio(
    "Continue as",
    options=["User", "Reviewer"],
    horizontal=True,
    key="selected_role",
)

st.divider()


# USER PORTAL

if role == "User":
    st.header("User Portal")

    user_id = st.text_input(
        "User ID",
        value=st.session_state.last_user_id,
        key="user_id_input",
        placeholder="Enter your permitted user ID",
    ).strip()

    st.session_state.last_user_id = user_id

    if not user_id:
        st.info("Enter your User ID to continue.")

    else:
        submit_tab, history_tab = st.tabs(
            ["Submit an idea", "My ideas"]
        )

        # SUBMIT NEW IDEA

        with submit_tab:
            st.subheader("Submit a new idea")

            with st.form("submit_idea_form", clear_on_submit=False):
                idea_text = st.text_area(
                    "Describe your idea",
                    height=180,
                    placeholder=(
                        "Describe the problem, proposed solution, "
                        "and expected benefit..."
                    ),
                )

                submit_idea = st.form_submit_button(
                    "Submit idea",
                    type="primary",
                )

            if submit_idea:
                if len(idea_text.strip()) < 10:
                    st.warning("Please enter at least 10 characters.")
                else:
                    result = api_request(
                        "POST",
                        "/user/ideas",
                        json_body={
                            "user_id": user_id,
                            "idea": idea_text.strip(),
                        },
                    )

                    if result is not None:
                        thread_id = result.get("thread_id")

                        if not thread_id:
                            st.error(
                                "The API did not return thread_id. "
                                "Check POST /user/ideas."
                            )
                        else:
                            st.session_state.active_task_id = None
                            st.session_state.active_thread_id = str(thread_id)
                            st.session_state.active_idea = result
                            st.session_state.active_idea_owner = user_id

                            st.success(
                                "Idea submitted. Please provide a draft summary."
                            )
                            st.rerun()

        # IDEA HISTORY

        with history_tab:
            st.subheader("My submitted ideas")

            if st.button("Refresh my ideas", key="refresh_user_ideas"):
                result = api_request(
                    "GET",
                    f"/user/{user_id}/ideas",
                )

                if result is not None:
                    st.session_state.user_ideas = result.get("ideas", [])

            ideas = st.session_state.user_ideas

            if ideas:
                st.dataframe(
                    [
                        {
                            "task_id": get_task_id(item),
                            "status": item.get("status"),
                        }
                        for item in ideas
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

                reference_to_item = {
                    str(idea_reference(item)): item
                    for item in ideas
                    if idea_reference(item)
                }

                references = list(reference_to_item.keys())

                if references:
                    selected_reference = st.selectbox(
                        "Select an idea to reopen",
                        options=references,
                        format_func=lambda value: idea_label(
                            reference_to_item[value]
                        ),
                        key="reopen_idea_reference",
                    )

                    if st.button(
                        "Open selected idea",
                        type="primary",
                        key="open_selected_idea",
                    ):
                        load_one_idea(user_id, selected_reference)

            else:
                st.caption(
                    "No ideas loaded yet. Select Refresh my ideas "
                    "to retrieve your submitted ideas."
                )

        render_user_idea(user_id)


# REVIEWER PORTAL

else:
    st.header("Reviewer Portal")

    reviewer_id = st.text_input(
        "Reviewer ID",
        value=st.session_state.last_reviewer_id,
        key="reviewer_id_input",
        placeholder="Enter your permitted reviewer ID",
    ).strip()

    st.session_state.last_reviewer_id = reviewer_id

    pending_tab, escalated_tab = st.tabs(
        ["Pending approvals", "Escalated approvals"]
    )

    with pending_tab:
        st.subheader("Pending approvals")

        if st.button("Refresh pending", key="refresh_pending"):
            if not reviewer_id:
                st.warning("Enter your Reviewer ID first.")
            else:
                result = api_request(
                    "GET",
                    "/reviewer/pending",
                    params={"reviewer_id": reviewer_id},
                )

                if result is not None:
                    st.session_state.pending_approvals = (
                        result.get("approvals", [])
                    )

        render_reviewer_queue(
            reviewer_id,
            "Pending approvals",
            st.session_state.pending_approvals,
            "pending",
        )

    with escalated_tab:
        st.subheader("Escalated approvals")

        if st.button("Refresh escalated", key="refresh_escalated"):
            if not reviewer_id:
                st.warning("Enter your Reviewer ID first.")
            else:
                result = api_request(
                    "GET",
                    "/reviewer/escalated",
                    params={"reviewer_id": reviewer_id},
                )

                if result is not None:
                    st.session_state.escalated_approvals = (
                        result.get("approvals", [])
                    )

        render_reviewer_queue(
            reviewer_id,
            "Escalated approvals",
            st.session_state.escalated_approvals,
            "escalated",
        )

st.divider()

st.caption(
    "Idea Triage Agent · Testing interface. "
    "Role IDs are validated by the API; this interface does not "
    "implement password-based login or session authentication."
)