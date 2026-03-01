import functools
import os

import streamlit as st
from vid_analyser.evals.model import TestCase
from vid_analyser.evals.store.local import LocalStore
from vid_analyser.evals.ui.labeler.golden_form import get_golden_form_options, render_golden_widget


def get_local_store() -> LocalStore:
    local_store_dir = os.getenv("LOCAL_STORE_DIR")
    if not local_store_dir:
        raise RuntimeError(
            "LOCAL_STORE_DIR not found in .env. Set LOCAL_STORE_DIR to a local directory containing videos for labelling."
        )
    return LocalStore(root=local_store_dir)


def page(case: str | TestCase) -> None:
    store = get_local_store()
    if isinstance(case, str):
        vid = store.get_video(case)
        video_key = case
    else:
        vid = store.get_video(case.video_path)
        video_key = case.video_path

    col1, col2 = st.columns([1, 2])

    with col1:
        st.video(vid, autoplay=True, loop=True)
    with col2:
        form_options = get_golden_form_options(store)
        existing_golden = case.golden if isinstance(case, TestCase) else None
        golden = render_golden_widget(form_options, existing_golden)
        if golden is not None:
            store.save_golden_case(golden, store.get_video(video_key), name=video_key)
            st.session_state.notify.append(video_key)
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="Golden Labeler", layout="wide")
    st.session_state.setdefault("notify", [])
    for video_key in st.session_state.notify:
        st.toast(f"Saved {video_key}", icon="✅")
        st.session_state.notify.remove(video_key)

    store = get_local_store()
    labelled_hashmap = store.labelled_hashmap
    video_hashmap = store.video_hashmap
    pages = []
    labelled_tally = []
    for video_hash, video_key in video_hashmap.items():
        is_labelled = video_hash in labelled_hashmap
        labelled_tally.append(is_labelled)
        label_status = "✅" if is_labelled else "❌"
        f = functools.partial(page, labelled_hashmap.get(video_hash, video_key))
        pages.append(
            st.Page(
                f,
                title=video_key,
                icon=label_status,
                url_path=video_key.replace("/", "_").replace(".", "_"),
            )
        )
    n_labelled = sum(labelled_tally)
    n_vids = len(labelled_tally)
    st.progress(n_labelled / n_vids if n_vids else 0.0, text=f"Labelled {n_labelled}/{n_vids}")
    navigation = st.navigation(pages, position="sidebar")
    navigation.run()


if __name__ == "__main__":
    main()
