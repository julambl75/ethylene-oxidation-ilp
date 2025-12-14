#bias(":- #count { X : in_body(X) } < 1.").
#bias(":- #count { X : in_body(X) } > 6.").

#bias(":- lb(X, Y1), lb(X, Y2), Y1 != Y2.").
#bias(":- ub(X, Y1), ub(X, Y2), Y1 != Y2.").

#bias("intermediate(rule_has_head(X)) :- in_head(X).").
#final_bias(":- possible_head(X), not intermediate(rule_has_head(X)).").

#bias("penalty(50, head(X)) :- in_head(X).").
#bias("penalty(5, body(X)) :- in_body(X).").

#bias("intermediate(chosen(S)) :- in_body(short_term_change(S,none)).").
#bias("intermediate(chosen(m2_pv)) :- in_body(measured_m2_pv(_)).").
#bias("intermediate(chosen(m2_pv)) :- in_body(short_term_change_up_m2_pv(_)).").
#bias("intermediate(chosen(m2_pv)) :- in_body(short_term_change_down_m2_pv(_)).").
#bias("intermediate(chosen(k1_p1)) :- in_body(measured_k1_p1(_)).").
#bias("intermediate(chosen(k1_p1)) :- in_body(short_term_change_up_k1_p1(_)).").
#bias("intermediate(chosen(k1_p1)) :- in_body(short_term_change_down_k1_p1(_)).").
#bias("intermediate(chosen(m3_pv)) :- in_body(measured_m3_pv(_)).").
#bias("intermediate(chosen(m3_pv)) :- in_body(short_term_change_up_m3_pv(_)).").
#bias("intermediate(chosen(m3_pv)) :- in_body(short_term_change_down_m3_pv(_)).").
#bias("intermediate(chosen(e2_tsi)) :- in_body(measured_e2_tsi(_)).").
#bias("intermediate(chosen(e2_tsi)) :- in_body(short_term_change_up_e2_tsi(_)).").
#bias("intermediate(chosen(e2_tsi)) :- in_body(short_term_change_down_e2_tsi(_)).").
#bias("intermediate(chosen(e2_tti)) :- in_body(measured_e2_tti(_)).").
#bias("intermediate(chosen(e2_tti)) :- in_body(short_term_change_up_e2_tti(_)).").
#bias("intermediate(chosen(e2_tti)) :- in_body(short_term_change_down_e2_tti(_)).").
#bias("intermediate(chosen(m1_pv)) :- in_body(measured_m1_pv(_)).").
#bias("intermediate(chosen(m1_pv)) :- in_body(short_term_change_up_m1_pv(_)).").
#bias("intermediate(chosen(m1_pv)) :- in_body(short_term_change_down_m1_pv(_)).").
#bias("intermediate(chosen(r1_t2)) :- in_body(measured_r1_t2(_)).").
#bias("intermediate(chosen(r1_t2)) :- in_body(short_term_change_up_r1_t2(_)).").
#bias("intermediate(chosen(r1_t2)) :- in_body(short_term_change_down_r1_t2(_)).").
#bias("intermediate(chosen(snk1_t)) :- in_body(measured_snk1_t(_)).").
#bias("intermediate(chosen(snk1_t)) :- in_body(short_term_change_up_snk1_t(_)).").
#bias("intermediate(chosen(snk1_t)) :- in_body(short_term_change_down_snk1_t(_)).").
#bias("intermediate(chosen(snk1_p)) :- in_body(measured_snk1_p(_)).").
#bias("intermediate(chosen(snk1_p)) :- in_body(short_term_change_up_snk1_p(_)).").
#bias("intermediate(chosen(snk1_p)) :- in_body(short_term_change_down_snk1_p(_)).").
#bias("intermediate(chosen(snk1_z_c2h4o)) :- in_body(measured_snk1_z_c2h4o(_)).").
#bias("intermediate(chosen(snk1_z_c2h4o)) :- in_body(short_term_change_up_snk1_z_c2h4o(_)).").
#bias("intermediate(chosen(snk1_z_c2h4o)) :- in_body(short_term_change_down_snk1_z_c2h4o(_)).").
#bias("intermediate(chosen(snk1_z_c2h4)) :- in_body(measured_snk1_z_c2h4(_)).").
#bias("intermediate(chosen(snk1_z_c2h4)) :- in_body(short_term_change_up_snk1_z_c2h4(_)).").
#bias("intermediate(chosen(snk1_z_c2h4)) :- in_body(short_term_change_down_snk1_z_c2h4(_)).").
#bias("intermediate(chosen(snk1_z_co2)) :- in_body(measured_snk1_z_co2(_)).").
#bias("intermediate(chosen(snk1_z_co2)) :- in_body(short_term_change_up_snk1_z_co2(_)).").
#bias("intermediate(chosen(snk1_z_co2)) :- in_body(short_term_change_down_snk1_z_co2(_)).").

#final_bias("chosen_cost(m2_pv, 100) :- intermediate(chosen(m2_pv)).").
#final_bias("chosen_cost(k1_p1, 32) :- intermediate(chosen(k1_p1)).").
#final_bias("chosen_cost(m3_pv, 32) :- intermediate(chosen(m3_pv)).").
#final_bias("chosen_cost(e2_tsi, 22) :- intermediate(chosen(e2_tsi)).").
#final_bias("chosen_cost(e2_tti, 22) :- intermediate(chosen(e2_tti)).").
#final_bias("chosen_cost(m1_pv, 22) :- intermediate(chosen(m1_pv)).").
#final_bias("chosen_cost(r1_t2, 22) :- intermediate(chosen(r1_t2)).").
#final_bias("chosen_cost(snk1_t, 22) :- intermediate(chosen(snk1_t)).").
#final_bias("chosen_cost(snk1_p, 32) :- intermediate(chosen(snk1_p)).").
#final_bias("chosen_cost(snk1_z_c2h4o, 224) :- intermediate(chosen(snk1_z_c2h4o)).").
#final_bias("chosen_cost(snk1_z_c2h4, 224) :- intermediate(chosen(snk1_z_c2h4)).").
#final_bias("chosen_cost(snk1_z_co2, 224) :- intermediate(chosen(snk1_z_co2)).").

% step 1
#final_bias("cost_pen(P) :- P = #sum { C, S: chosen_cost(S, C) }.").
#final_bias("coverage_pen(Cnt*100) :- Cnt = #count { X: n_cov(X), not nominal_eg(X) }.").
#final_bias("n_sensors(N) :- N = #count { S: chosen_cost(S, _) }.").

% step 2 - alpha=10, beta=1.05
%#final_bias("optimal_coverage_pen(?).").
%#final_bias(":~ cost_pen(P). [P*10@0]").
%#final_bias(":- optimal_coverage_pen(Po), coverage_pen(P), P*100 > Po*105.").

% debugging
%#final_bias("#show cost_pen/1.").
%#final_bias("#show coverage_pen/1.").
%#final_bias("#show n_sensors/1.").

