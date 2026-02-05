if [ $(basename $PWD) = 'validate' ]; then
  :
elif [ -d 'validate' ]; then
  cd validate
else
  echo 'Please navigate to validate/, exiting...'
  exit 1
fi

# ---

BASE_OPTS="-lm fail -e highSetpoint_flowControlLoop highSetpoint_tempControlLoop leak_beforeCompressor lowSetpoint_flowControlLoop lowSetpoint_tempControlLoop missingEthylene_source missingOxygen_source stuckClosed_coolingWaterOutValve stuckClosed_tempControlValve stuckOpen_tempControlValve nominal -nu -mr 125 -st 6 -m cost_opt_dynamic -md dynamic -op m2_pv k1_p1 m3_pv e2_tsi e2_tti m1_pv r1_t2 snk1_t snk1_p snk1_z_c2h4o snk1_z_c2h4 snk1_z_co2 -t 0.2"

if [ "$1" == "--step1" ]; then
  echo "Running script without cost optimization to extract value from coverage_pen/1..."
  source ~/miniconda3/etc/profile.d/conda.sh
  conda activate exothermic
  if [ "$?" -gt 0 ]; then
    echo "Problem activating conda environment, exiting!"
    exit 1
  fi

  script_dir=$(dirname "$0")
  cd $script_dir
  echo "Generating new train.las..."
  python ../../databases/read_db/gen_bk.py $BASE_OPTS
  echo "Now, follow the instructions in ../logic/cost_opt_dynamic/README.md"
  exit 0
elif [ "$#" -ge 1 ]; then
  echo "Invalid option(s) passed, exiting..."
  exit 1
fi

# ---

# value extracted from coverage_pen/1 from the optimal solution after running `FastLAS --opl train.las bias.las --output-solve-program | clingo`
REF_COV_PEN=60800

base_cmd="./validate.sh $BASE_OPTS"

# comment out some of these to avoid running all of them if desired (very slow for large beta)
alpha_beta_options=("--alpha 10 --beta 1.1" "--alpha 10 --beta 1.25" "--alpha 100 --beta 1.1" "--alpha 100 --beta 1.25" "--alpha 500 --beta 1.1" "--alpha 500 --beta 1.25" "--alpha 1000 --beta 1.1" "--alpha 1000 --beta 1.25")
num_sensors_options=("--num-sensors 5" "--num-sensors 4" "--num-sensors 3" "--num-sensors 2" "--num-sensors 1")

cmds=("$base_cmd -ocp $REF_COV_PEN --no-prob")

# try alpha and beta variations, with cost optimization
for ((i=0; i < ${#alpha_beta_options[@]}; i++)); do
  alpha_beta_option="${alpha_beta_options[i]}"
  cmds+=("$base_cmd $alpha_beta_option -ocp $REF_COV_PEN --no-prob")
done

# require specific number of sensors, ignoring cost optimization (alpha and beta unused)
for ((i=0; i < ${#num_sensors_options[@]}; i++)); do
  num_sensors_option="${num_sensors_options[i]}"
  cmds+=("$base_cmd $num_sensors_option --no-prob")
done

for cmd in "${cmds[@]}"; do
  echo "Running: $cmd"
  $cmd
done


