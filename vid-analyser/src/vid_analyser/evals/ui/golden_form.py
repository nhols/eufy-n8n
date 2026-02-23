from dataclasses import dataclass
from typing import cast

import streamlit as st

from vid_analyser.evals.model import Golden
from vid_analyser.evals.store.local import LocalStore
from vid_analyser.llm.response_model import IRMode, ParkingSpotStatus


@dataclass(frozen=True)
class GoldenFormOptions:
    number_plate: list[str]
    event_checklist: list[str]
    people: list[str]


@dataclass(frozen=True)
class GoldenFormDefaults:
    ir_mode: IRMode = "no"
    parking_spot_status: ParkingSpotStatus = "vacant"
    number_plate: str | None = None
    event_checklist: tuple[str, ...] = ()
    people: tuple[str, ...] = ()
    send_notification: bool = True

    @classmethod
    def from_golden(cls, golden_case: Golden | None) -> "GoldenFormDefaults":
        if golden_case is None:
            return cls()
        return cls(
            ir_mode=golden_case.ir_mode,
            parking_spot_status=golden_case.parking_spot_status,
            number_plate=golden_case.number_plate,
            event_checklist=tuple(golden_case.event_checklist),
            people=tuple(golden_case.people),
            send_notification=golden_case.send_notification,
        )


def get_golden_form_options(store: LocalStore) -> GoldenFormOptions:
    cases = store.get_labelled_cases()
    return GoldenFormOptions(
        number_plate=sorted({case.golden.number_plate for case in cases if case.golden.number_plate}),
        event_checklist=sorted({event for case in cases for event in case.golden.event_checklist}),
        people=sorted({person for case in cases for person in case.golden.people}),
    )


def _merge_selected_options(options: list[str], selected: tuple[str, ...]) -> list[str]:
    return list(dict.fromkeys([*selected, *options]))


def _number_plate_options(options: GoldenFormOptions, default_number_plate: str | None) -> list[str]:
    number_plate_options = options.number_plate
    if default_number_plate and default_number_plate not in number_plate_options:
        number_plate_options = [default_number_plate, *number_plate_options]
    return ["", *number_plate_options]


def render_golden_widget(
    options: GoldenFormOptions,
    golden_case: Golden | None = None,
    *,
    form_key: str = "golden_form",
) -> Golden | None:
    defaults = GoldenFormDefaults.from_golden(golden_case)

    with st.form(form_key):
        ir_mode_values = list(IRMode.__args__)
        parking_spot_status_values = list(ParkingSpotStatus.__args__)
        selected_ir_mode = st.selectbox(
            "IR Mode",
            options=ir_mode_values,
            index=ir_mode_values.index(defaults.ir_mode),
        )
        selected_parking_spot_status = st.selectbox(
            "Parking Spot Status",
            options=parking_spot_status_values,
            index=parking_spot_status_values.index(defaults.parking_spot_status),
        )
        number_plate_values = _number_plate_options(options, defaults.number_plate)
        selected_number_plate = st.selectbox(
            "Number Plate (if any)",
            options=number_plate_values,
            index=number_plate_values.index(defaults.number_plate or ""),
            accept_new_options=True,
        )
        selected_event_checklist = st.multiselect(
            "Event Checklist (one item per line)",
            options=_merge_selected_options(options.event_checklist, defaults.event_checklist),
            default=list(defaults.event_checklist),
            accept_new_options=True,
        )
        selected_people = st.multiselect(
            "People (one name per line)",
            options=_merge_selected_options(options.people, defaults.people),
            default=list(defaults.people),
            accept_new_options=True,
        )
        selected_send_notification = st.checkbox(
            "Send Notification",
            value=defaults.send_notification,
        )
        submitted = st.form_submit_button(":material/save:")

    if not submitted:
        return None

    return Golden(
        ir_mode=cast("IRMode", selected_ir_mode),
        parking_spot_status=cast("ParkingSpotStatus", selected_parking_spot_status),
        number_plate=selected_number_plate or None,
        event_checklist=selected_event_checklist,
        people=selected_people,
        send_notification=selected_send_notification,
    )
