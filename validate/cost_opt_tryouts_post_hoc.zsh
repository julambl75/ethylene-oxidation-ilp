#!/bin/zsh

if [[ ${PWD:t} == validate ]]; then
  :  # noop
elif [[ -d validate ]]; then
  cd validate
else
  echo 'Please navigate to validate/, exiting...'
  exit 1
fi

if [[ $ZSH_EVAL_CONTEXT != *:file ]]; then
  # only run main script if we are not doing `source`ing this script to access results_dir_to_cost()
  base_cmd="./validate.sh -lm fail"
  e_opt="-e highSetpoint_flowControlLoop highSetpoint_tempControlLoop leak_beforeCompressor lowSetpoint_flowControlLoop lowSetpoint_tempControlLoop missingEthylene_source missingOxygen_source stuckClosed_coolingWaterOutValve stuckClosed_tempControlValve stuckOpen_tempControlValve nominal"
  nu_nb_opt="-nu"
  mr_opt="-mr 125"
  st_opt="-st 6"
  stf_opt="-stf ../../database/short_terms.csv"
  mode_opt="-m dynamic"
  t_opt="-t 0.2"
  fi_opt=""

    echo $mode_opt
  op_opts=()
  while IFS= read -r answer_set; do
    sensors=$(echo "$answer_set" | tr ' ' '\n' | grep '^chosen(' | sed -E 's/chosen\(([^,]+).*/\1/' | paste -sd ' ' -)
    op_opts+=("$sensors")
  done < <(clingo cost_opt_sensor_choices.asp -n 0 | grep 'n_chosen')

  for op_opt in "${op_opts[@]}"; do
    cmd="$base_cmd $e_opt $nu_nb_opt $mr_opt $st_opt $stf_opt $mode_opt $t_opt $fi_opt -op $op_opt"
    echo "Running: $cmd"
    eval "$cmd"
  done
else
  typeset -A cost_map
  while IFS= read -r match; do
    sensor=${match%% *}
    cost=${match#* }
    cost_map[$sensor]=$cost
  done < <(sed -En 's/^cost\(([a-zA-Z0-9_]+),[0-9]+,([0-9]+).*/\1 \2/p' cost_opt_sensor_choices.asp)
fi

# NOTE to extract sensors from results dir:
results_dir_to_cost() {
  ops=($(sed -E 's/.*-op ([^-]+)(-.*)?$/\1/' "$1/args.txt" | tr ' ' '\n'))
  local sum=0
  for sensor in "${ops[@]}"; do
    (( sum += ${cost_map[$sensor]:-0} ))
  done
  echo "$sum"
}

