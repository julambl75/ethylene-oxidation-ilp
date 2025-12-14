#!/bin/zsh

source cost_opt_tryouts_post_hoc.zsh

dir=$1
echo 'timestamp,n,nu,nb,n_runs,st,stf,m,op,oc,t,fi,n_rules,avg_body_len,avg_rule_prob,med_rule_prob,avg_rules_per_cl,avg_acc,min_auc,avg_auc,svm_acc,mlp_acc,random_forest_acc,hist_gradient_acc,ada_boost_acc,op_sensors,cost'

for subdir in $dir/*(N/); do
  [[ $subdir != *2025* ]] && continue
  [[ ! -f "$subdir/baseline.txt" ]] && continue

  args=(${(z)"$(<"$subdir/args.txt")"})
  numeric=false
  special_short_term=false
  real_world=false
  only_sensors=false
  n_classes=0
  n_buckets=""
  dataset_size=""
  short_term=""
  mode=""
  test_split=""
  filter_important=""

  i=1
  while (( i <= $#args )); do
    case "${args[i]}" in
      -e)
        j=$((i + 1))
        while (( j <= $#args )) && [[ ${args[j]} != -* ]]; do
          ((n_classes++))
          ((j++))
        done
        ;;
      -nu)
        numeric=true
        ;;
      -nb)
        n_buckets="${args[$((i+1))]}"
        ;;
      -mr)
        dataset_size="${args[$((i+1))]}"
        ;;
      -st)
        short_term="${args[$((i+1))]}"
        ;;
      -stf)
        special_short_term=true
        ;;
      -m)
        mode="${args[$((i+1))]}"
        ;;
      -op)
        real_world=true
        op_sensors=()
        j=$((i + 1))
        while (( j <= $#args )) && [[ ${args[j]} != -* ]]; do
          op_sensors+=("${args[j]}")
          ((j++))
        done
        ;;
      -oc)
        only_sensors=true
        ;;
      -t)
        test_split="${args[$((i+1))]}"
        ;;
      -fi)
        filter_important="${args[$((i+1))]}"
        ;;
    esac
    ((i++))
  done

  # read metrics
  metrics=$(<"$subdir/metrics.txt")
  n_rules=$(echo "$metrics" | grep -m1 'Number of rules' | sed 's/.*: //')
  avg_body_len=$(echo "$metrics" | grep -m1 'Average length of body' | sed 's/.*: //')
  avg_rule_prob=$(echo "$metrics" | grep -m1 'Average rule probability' | sed 's/.*: //')
  med_rule_prob=$(echo "$metrics" | grep -m1 'Median rule probability' | sed 's/.*: //')
  avg_rules_per_cl=$(echo "$metrics" | grep -m1 'Average number of rules per class' | sed 's/.*: //')
  avg_acc=$(echo "$metrics" | grep 'Accuracy' | sed 's/.*: //' | awk '{s+=$1} END{if(NR>0) print s/NR}')
  min_auc=$(echo "$metrics" | grep 'AUC' | sed 's/.*: //' | sort -n | head -n1)
  avg_auc=$(echo "$metrics" | grep 'AUC' | sed 's/.*: //' | awk '{s+=$1} END{if(NR>0) print s/NR}')

  # read baseline
  baseline=$(<"$subdir/baseline.txt")
  svm_acc=$(echo "$baseline" | grep -m1 'svm' | sed 's/.*: //')
  mlp_acc=$(echo "$baseline" | grep -m1 'mlp' | sed 's/.*: //')
  random_forest_acc=$(echo "$baseline" | grep -m1 'random_forest' | sed 's/.*: //')
  hist_gradient_acc=$(echo "$baseline" | grep -m1 'hist_gradient' | sed 's/.*: //')
  ada_boost_acc=$(echo "$baseline" | grep -m1 'ada_boost' | sed 's/.*: //')

  # compute cost
  cost=$(results_dir_to_cost "$subdir")

  timestamp=$(basename "$subdir")
  echo "$timestamp,$n_classes,$numeric,$n_buckets,$dataset_size,$short_term,$special_short_term,$mode,$real_world,$only_sensors,$test_split,$filter_important,$n_rules,$avg_body_len,$avg_rule_prob,$med_rule_prob,$avg_rules_per_cl,$avg_acc,$min_auc,$avg_auc,$svm_acc,$mlp_acc,$random_forest_acc,$hist_gradient_acc,$ada_boost_acc,${(j:\t:)op_sensors},$cost"
done

