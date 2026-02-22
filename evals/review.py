"""Streamlit dashboard for reviewing and correcting eval test cases.

Run with:
    streamlit run evals/review.py
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st
import yaml

TEST_CASES_DIR = Path("evals/test_cases")

IR_MODES = ["yes", "no", "unknown"]
PARKING_STATUSES = ["occupied", "vacant", "car entering", "car leaving", "unknown"]


def load_test_cases() -> list[Path]:
    return sorted(TEST_CASES_DIR.glob("*.yaml"))


def load_yaml(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def save_yaml(path: Path, data: dict) -> None:
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def is_reviewed(tc: dict) -> bool:
    criteria = tc.get("judge_criteria") or {}
    for vals in criteria.values():
        for s in (vals if isinstance(vals, list) else [vals]):
            if "TODO" in str(s):
                return False
    return True


def make_page_fn(tc_path: Path, idx: int, total: int, all_pages: list):
    """Create a page callable for a single test case."""

    def page():
        tc = load_yaml(tc_path)
        reviewed = is_reviewed(tc)

        # Status banner
        if reviewed:
            st.success(f"✅ This clip has been reviewed — {tc_path.stem}")
        else:
            st.info(f"🔴 This clip needs review — {tc_path.stem}")

        # Video + form layout
        col_video, col_form = st.columns([1, 1])

        with col_video:
            video_path = Path(tc["video_path"])
            if video_path.exists():
                st.video(str(video_path))
            else:
                st.warning(f"Video not found: {video_path}")

            # Metadata
            st.subheader("Metadata")
            meta = tc.get("metadata", {})
            st.text(f"Timestamp: {meta.get('local_datetime', 'N/A')}")
            bookings = meta.get("bookings", [])
            if bookings:
                for b in bookings:
                    st.text(
                        f"  {b['driver_name']} | {b['vehicle_registration']} | "
                        f"{b['vehicle_colour']} {b['vehicle_make']} {b['vehicle_model']}\n"
                        f"  {b['start_time']} → {b['end_time']}"
                    )
            else:
                st.text("  No bookings for this date")

            # Model reference output
            model_desc = tc.get("_model_events_description")
            model_summary = tc.get("_model_summary")
            if model_desc or model_summary:
                st.subheader("Model Reference Output")
                if model_desc:
                    st.caption("events_description")
                    st.info(model_desc)
                if model_summary:
                    st.caption("summary")
                    st.info(model_summary)

            if tc.get("_error"):
                st.error(f"Bootstrap error: {tc['_error']}")

        with col_form:
            st.subheader("Expected Values")
            expected = tc.get("expected", {})

            with st.form("edit_form"):
                ir_mode = st.selectbox(
                    "ir_mode",
                    IR_MODES,
                    index=IR_MODES.index(expected.get("ir_mode", "unknown")),
                )
                parking = st.selectbox(
                    "parking_spot_status",
                    PARKING_STATUSES,
                    index=PARKING_STATUSES.index(expected.get("parking_spot_status", "unknown")),
                )
                plate = st.text_input(
                    "number_plate (blank = null)",
                    value=expected.get("number_plate") or "",
                )
                notify = st.checkbox(
                    "send_notification",
                    value=expected.get("send_notification", False),
                )

                st.divider()
                st.subheader("Judge Criteria")
                criteria = tc.get("judge_criteria", {})

                events_criteria = st.text_area(
                    "events_description criteria (one per line)",
                    value="\n".join(criteria.get("events_description", [])),
                    height=120,
                )
                summary_criteria = st.text_area(
                    "summary criteria (one per line)",
                    value="\n".join(criteria.get("summary", [])),
                    height=120,
                )

                submitted = st.form_submit_button("💾 Save", type="primary", use_container_width=True)

            if submitted:
                tc["expected"] = {
                    "ir_mode": ir_mode,
                    "parking_spot_status": parking,
                    "number_plate": plate.strip() if plate.strip() else None,
                    "send_notification": notify,
                }
                tc["judge_criteria"] = {
                    "events_description": [line for line in events_criteria.splitlines() if line.strip()],
                    "summary": [line for line in summary_criteria.splitlines() if line.strip()],
                }
                save_yaml(tc_path, tc)
                st.rerun()

        # Nav buttons outside the form
        col_prev, col_spacer, col_next = st.columns([1, 2, 1])
        with col_prev:
            if idx > 0:
                if st.button("← Previous", use_container_width=True):
                    st.switch_page(all_pages[idx - 1])
        with col_next:
            if idx < total - 1:
                if st.button("Next →", use_container_width=True):
                    st.switch_page(all_pages[idx + 1])

    return page


def main() -> None:
    cases = load_test_cases()
    if not cases:
        st.error(f"No YAML files found in {TEST_CASES_DIR}")
        st.stop()

    # Build all pages first (need the list for switch_page references)
    pages: list[st.Page] = []
    for i, tc_path in enumerate(cases):
        tc = load_yaml(tc_path)
        icon = "✅" if is_reviewed(tc) else "🔴"
        # Create page — pass pages list (will be populated before run)
        pg = st.Page(
            make_page_fn(tc_path, i, len(cases), pages),
            title=tc_path.stem,
            icon=icon,
            url_path=tc_path.stem,
            default=(i == 0),
        )
        pages.append(pg)

    reviewed = sum(1 for c in cases if is_reviewed(load_yaml(c)))
    st.progress(reviewed / len(cases), text=f"**{reviewed}/{len(cases)}** reviewed")

    selected = st.navigation(pages)
    selected.run()


if __name__ == "__main__":
    main()
