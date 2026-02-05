# Cost Extension: How to Run

1. Update the reference coverage penalty (if necessary)
  a. Make sure your working directory is where this README file is located
  b. Generate fresh .las files for the task: `../../validate/cost_opt_tryouts_embedded.sh --step1`
  c. Search for the lowest possible example coverage penalty (up to 2h): `FastLAS --opl train.las bias.las bias_extra.las --output-solve-program | clingo`
  d. Extract the value inside the last 'coverage_pen/1'
  e. Open '../run_scripts/tryout_cost_optimize.sh' and assign `REF_COV_PEN` to the extracted value
2. Activate the cost constraint and try different variations
  a. `../../validate/cost_opt_tryouts_embedded.sh`
  b. See the results in '~/Desktop/results/'
