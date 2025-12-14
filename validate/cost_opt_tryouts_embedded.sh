if [ $(basename $PWD) = 'validate' ]; then
  :
elif [ -d 'validate' ]; then
  cd validate
else
  echo 'Please navigate to validate/, exiting...'
  exit 1
fi

REF_COV_PEN=61710 # example coverage penalty before adding cost-based restrictions (regenerate using FastLAS `--debug` mode)

base_cmd="./validate.sh -lm fail -e highSetpoint_flowControlLoop highSetpoint_tempControlLoop leak_beforeCompressor lowSetpoint_flowControlLoop lowSetpoint_tempControlLoop missingEthylene_source missingOxygen_source stuckClosed_coolingWaterOutValve stuckClosed_tempControlValve stuckOpen_tempControlValve nominal -nu -mr 125 -st 6 -m cost_opt_dynamic -md dynamic -op m2_pv k1_p1 m3_pv e2_tsi e2_tti m1_pv r1_t2 snk1_t snk1_p snk1_z_c2h4o snk1_z_c2h4 snk1_z_co2 -t 0.2"

#alpha_options=("" "--alpha 1" "--alpha 5" "--alpha 20" "--alpha 50" "--alpha 100" "--alpha 500")
alpha_options=("" "--alpha 1" "--alpha 5" "--alpha 20" "--alpha 50" "--alpha 100")
beta_options=("" "--beta 1.01" "--beta 1.02" "--beta 1.1" "--beta 1.2" "--beta 1.5")

num_sensors_options=("--num-sensors 6" "--num-sensors 5" "--num-sensors 4" "--num-sensors 3" "--num-sensors 2" "--num-sensors 1")

cmds=("$base_cmd -ocp $REF_COV_PEN --no-prob")

# try alpha and beta variations
for ((i=1; i < ${#alpha_options[@]}; i++)); do
  alpha_option="${alpha_options[i]}"
  cmds+=("$base_cmd $alpha_option -ocp $REF_COV_PEN --no-prob")
done
for ((i=1; i < ${#beta_options[@]}; i++)); do
  beta_option="${beta_options[i]}"
  cmds+=("$base_cmd $beta_option -ocp $REF_COV_PEN --no-prob")
done

# optimize for cost as well, given example coverage threshold
for ((i=1; i < ${#num_sensors_options[@]}; i++)); do
  num_sensors_option="${num_sensors_options[i]}"
  cmds+=("$base_cmd $num_sensors_option -ocp $REF_COV_PEN --no-prob")
done

# ignore cost
for ((i=1; i < ${#num_sensors_options[@]}; i++)); do
  num_sensors_option="${num_sensors_options[i]}"
  cmds+=("$base_cmd $num_sensors_option --no-prob")
done

for cmd in "${cmds[@]}"; do
  echo "Running: $cmd"
  $cmd
done

