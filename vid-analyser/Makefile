.PHONY: eval-labeler eval-results

eval-labeler:
	PYTHONPATH=src uv run streamlit run src/vid_analyser/evals/ui/labeler/app.py

eval-results:
	PYTHONPATH=src uv run streamlit run src/vid_analyser/evals/ui/results/app.py
