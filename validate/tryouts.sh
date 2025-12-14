if [ $(basename $PWD) = 'validate' ]; then
  :
elif [ -d 'validate' ]; then
  cd validate
else
  echo 'Please navigate to validate/, exiting...'
  exit 1
fi

base_cmd="./validate.sh -lm fail"

# In the below groups of options, the first option is always default

e_options=(
  "-e missingEthylene_source lowSetpoint_flowControlLoop lowSetpoint_tempControlLoop leak_beforeCompressor lowPressure_coolingWater stuckClosed_coolingWaterOutValve nominal"
  "-e highSetpoint_flowControlLoop highSetpoint_tempControlLoop leak_beforeCompressor lowSetpoint_flowControlLoop lowSetpoint_tempControlLoop missingEthylene_source missingOxygen_source stuckClosed_coolingWaterOutValve stuckClosed_tempControlValve stuckOpen_tempControlValve nominal"
  "-e lowPressure_source highTemp_source lowTemp_source highTemp_coolingWater lowTemp_coolingWater nominal"
)

nu_nb_options=("-nu" "-nb 5" "-nb 3" "-nb 9")

mr_options=("-mr 75" "-mr 10" "-mr 25" "-mr 50" "-mr 125")

st_options=("-st 6" "-st 2" "-st 4" "-st 10" "-st 20")

stf_options=("" "-stf ../../database/read_db/short_terms.csv")

mode_options=("-m dynamic" "-m dynamic_disabledFlowController" "-m dynamic_disabledTempController" "-m dynamic_disabledFlowController_disabledTempController")

oc_op_options=("-op e2_tsi e2_tti k1_p1 m1_pv m2_pv m3_pv r1_t2 snk1_p snk1_t srcr1_p srcr1_t" "-oc m1 m2 m3" "")

t_options=("-t 0.2" "-t 0.05" "-t 0.1" "-t 0.4")

fi_options=("" "-fi 3" "-fi 5" "-fi 7")


cmds=("$base_cmd ${e_options[0]} ${nu_nb_options[0]} ${mr_options[0]} ${st_options[0]} ${stf_options[0]} ${mode_options[0]} ${oc_op_options[0]} ${t_options[0]} ${fi_options[0]}")
#${cmds[0]}
#exit

for ((i=1; i < ${#e_options[@]}; i++)); do
  e_option="${e_options[i]}"
  cmds+=("$base_cmd $e_option ${nu_nb_options[0]} ${mr_options[0]} ${st_options[0]} ${stf_options[0]} ${mode_options[0]} ${oc_op_options[0]} ${t_options[0]} ${fi_options[0]}")
done

for ((i=1; i < ${#nu_nb_options[@]}; i++)); do
  nu_nb_option="${nu_nb_options[i]}"
  cmds+=("$base_cmd ${e_options[0]} $nu_nb_option ${mr_options[0]} ${st_options[0]} ${stf_options[0]} ${mode_options[0]} ${oc_op_options[0]} ${t_options[0]} ${fi_options[0]}")
done

for ((i=1; i < ${#mr_options[@]}; i++)); do
  mr_option="${mr_options[i]}"
  cmds+=("$base_cmd ${e_options[0]} ${nu_nb_options[0]} $mr_option ${st_options[0]} ${stf_options[0]} ${mode_options[0]} ${oc_op_options[0]} ${t_options[0]} ${fi_options[0]}")
done

for ((i=1; i < ${#st_options[@]}; i++)); do
  st_option="${st_options[i]}"
  cmds+=("$base_cmd ${e_options[0]} ${nu_nb_options[0]} ${mr_options[0]} $st_option ${stf_options[0]} ${mode_options[0]} ${oc_op_options[0]} ${t_options[0]} ${fi_options[0]}")
done

for ((i=1; i < ${#stf_options[@]}; i++)); do
  stf_option="${stf_options[i]}"
  cmds+=("$base_cmd ${e_options[0]} ${nu_nb_options[0]} ${mr_options[0]} ${st_options[0]} $stf_option ${mode_options[0]} ${oc_op_options[0]} ${t_options[0]} ${fi_options[0]}")
done

for ((i=1; i < ${#mode_options[@]}; i++)); do
  mode_option="${mode_options[i]}"
  cmds+=("$base_cmd ${e_options[0]} ${nu_nb_options[0]} ${mr_options[0]} ${st_options[0]} ${stf_options[0]} $mode_option ${oc_op_options[0]} ${t_options[0]} ${fi_options[0]}")
done

for ((i=1; i < ${#oc_op_options[@]}; i++)); do
  oc_op_option="${oc_op_options[i]}"
  cmds+=("$base_cmd ${e_options[0]} ${nu_nb_options[0]} ${mr_options[0]} ${st_options[0]} ${stf_options[0]} ${mode_options[0]} $oc_op_option ${t_options[0]} ${fi_options[0]}")
done

#for ((i=1; i < ${#t_options[@]}; i++)); do
#  t_option="${t_options[i]}"
#  cmds+=("$base_cmd ${e_options[0]} ${nu_nb_options[0]} ${mr_options[0]} ${st_options[0]} ${stf_options[0]} ${mode_options[0]} ${oc_op_options[0]} $t_option ${fi_options[0]}")
#done
#
#for ((i=1; i < ${#fi_options[@]}; i++)); do
#  fi_option="${fi_options[i]}"
#  cmds+=("$base_cmd ${e_options[0]} ${nu_nb_options[0]} ${mr_options[0]} ${st_options[0]} ${stf_options[0]} ${mode_options[0]} ${oc_op_options[0]} ${t_options[0]} $fi_option")
#done

for cmd in "${cmds[@]}"; do
  echo "Running: $cmd"
  $cmd
done

