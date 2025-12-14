CONDA_PATH=~/miniconda3/etc/profile.d/conda.sh
CONDA_ENV=exothermic

if [ $(basename $PWD) = 'validate' ]; then
  :
elif [ -d 'validate' ]; then
  cd validate
else
  echo 'Please navigate to validate/, exiting...'
  exit 1
fi

N_CUTOFFS=10
CUTOFFS=$(for i in `seq 0 $(echo 1/$N_CUTOFFS | bc -l) 1`; do echo $i; done)

BIAS_LAS='bias.las'
BIAS_EXTRA_LAS='bias_extra.las'
TRAIN_LAS='train.las'
CLASSES_ASP='classes.asp'
COUNT_BIN_CLASS_ASP='../validate/count_binary_classif.asp'
CONFUSION_CSV='confusion_matrix.csv'

RESULTS_PATH=~/Desktop/results/$(date "+%Y-%m-%d_%H-%M-%S")
mkdir -p $RESULTS_PATH
echo "$@" > $RESULTS_PATH/args.txt

# weird bug where FastLAS breaks when conda is activated
source $CONDA_PATH
conda activate $CONDA_ENV

if [[ $* == *--no-prob* ]]; then
  prob_solve_arg=""
  echo "Disabling probabilistic mode..."
  new_args=()
  for arg in "$@"; do
    if [[ "$arg" != "--no-prob" ]]; then
      new_args+=("$arg")
    fi
  done
  set -- "${new_args[@]}"
else
  prob_solve_arg="--prob-solve"
fi

if [[ $* == *--skip* ]]; then
  echo "Skipping data generation step..."
else
  echo "Generating new train/test code..."
  python3 ../database/generate_task.py "$@"
  if [ $? -ne 0 ]; then
    echo "Error: invalid arguments supplied"
    exit
  fi
fi

# run everything from logic/, but it means we need to adjust the path for short terms
cd ../logic

mode=$(echo $@ | grep -o -e '-m [a-z_]\+' | awk '{print $2}')
if [ ! "$(ls $mode/test)" ]; then
  echo "No classes found, maybe you did not pass a train split?"
  exit
fi

conda deactivate

echo "Running FastLAS..."
las_output=$(time FastLAS --opl $prob_solve_arg $mode/$BIAS_LAS $mode/$BIAS_EXTRA_LAS $mode/$TRAIN_LAS) # --weight-probability-priors 1
rules=$(echo "$las_output" | grep ':-')
echo "$rules" > $RESULTS_PATH/rules.txt
echo "$rules"

conda activate $CONDA_ENV

echo "Computing rule metrics..."
metrics=$(python3 ../validate//compute_metrics.py "$rules")
metrics_path=$RESULTS_PATH/metrics.txt
echo "$metrics" > $metrics_path
echo "$metrics"

echo "Saving rules with probability >= cutoff to learned_<cutoff>.las for each cutoff..."
rm $mode/learned_*.asp
for cutoff in $CUTOFFS; do
  touch $mode/learned_$cutoff.asp
  echo "$rules" |
    while IFS= read -r line; do
      if [[ "$line" =~ ^[0-9.]+: ]]; then
        prob=$(echo "$line" | grep -o -E '^[0-9.]+')
        rule=$(echo "$line" | grep -o -E ':.*' | cut -c2-)
      else
        prob=1
        rule="$line"
      fi
      if (( $(echo "$prob <= $cutoff" | bc -l) )); then
        echo $rule | sed 's/^/predicted(/;s/ /) /' >> $mode/learned_$cutoff.asp
      fi
  done
  echo "prediction :- predicted(_). prediction(no_failures) :- not prediction." >> $mode/learned_$cutoff.asp
done

echo "Running clingo for every sample of every experiment and filling confusion matrices..."
classes=("$(ls -1 $mode/test | grep '.las$' | sed 's/:.*//' | uniq)")
echo 'class,cutoff,tp,tn,fp,fn' > $mode/$CONFUSION_CSV
for class in $classes; do
  for cutoff in $CUTOFFS; do
    ls -1 $mode/test | grep "^$class:\d\+.las" |
      while IFS= read -r test_file; do
        # extract shown model predicates and increment respective variables accordingly
        eval $(clingo $mode/test/$test_file $mode/learned_$cutoff.asp $mode/$CLASSES_ASP $COUNT_BIN_CLASS_ASP 2> /dev/null | grep -iB1 'SATISFIABLE' | head -n 1 | sed 's/n_//g;s/(/=/g;s/)/;/g')
        echo "$class,$cutoff,$tp,$tn,$fp,$fn" >> $mode/$CONFUSION_CSV
      done
  done
done
cp $mode/$CONFUSION_CSV $RESULTS_PATH/$CONFUSION_CSV
python3 ../validate/confusion_matrix.py -m $mode -s $RESULTS_PATH

echo "Generating ROC graphs..."
echo '' >> $metrics_path
python3 ../validate/plot_roc.py $mode/$CONFUSION_CSV $RESULTS_PATH $metrics_path

args=("$@")
gen_validation_examples_cmd="python3 ../validate/gen_validation_examples.py"
skip=0
for ((i=0; i<${#args[@]}; i++)); do
    if [[ $skip -gt 0 ]]; then
        ((skip--))
        continue
    fi
    case "${args[$i]}" in
        -lm|-fi|--alpha|--beta|-ocp|--num-sensors)
            skip=1  # skip flag and its value
            ;;
        -nu|--skip)
            # skip flag only (no argument)
            ;;
        -stf)
            # remove extra ../ now that we have `cd`ed up
            gen_validation_examples_cmd+=" ${args[$i]} ${args[$i+1]#../}"
            skip=1
            ;;
        *)
            gen_validation_examples_cmd+=" ${args[$i]}"
            ;;
    esac
done
gen_validation_examples_cmd+=" -r $RESULTS_PATH/rules.txt -d $RESULTS_PATH -p scores -ng"

echo "Computing scores..."
scoring_out=$(eval "$gen_validation_examples_cmd")
echo "$scoring_out" > $RESULTS_PATH/scoring.txt
echo "$scoring_out"

baseline_cmd="python3 ../baseline/run_baseline.py"
skip=0
for ((i=0; i<${#args[@]}; i++)); do
    if [[ $skip -gt 0 ]]; then
        ((skip--))
        continue
    fi
    case "${args[$i]}" in
        -lm|-fi|--alpha|--beta|-ocp|--num-sensors)
            skip=1  # skip flag and its value
            ;;
        -nu|--skip)
            # skip flag only (no argument)
            ;;
        -stf)
            # remove extra ../ now that we have `cd`ed up
            baseline_cmd+=" ${args[$i]} ${args[$i+1]#../}"
            skip=1
            ;;
        *)
            baseline_cmd+=" ${args[$i]}"
            ;;
    esac
done
baseline_cmd+=" -cm $mode/confusion_matrix.csv -s $RESULTS_PATH"

echo "Comparing with baselines..."
baseline_out=$(eval "$baseline_cmd")
echo "$baseline_out" > $RESULTS_PATH/baseline.txt
echo "$baseline_out"

