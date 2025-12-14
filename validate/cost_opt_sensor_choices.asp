% cost(<sensor>,<sqrt_cost>,<cost>).
% we want to focus on nontrivial faults, so only include sensors that are useful for more than 1 fault
cost(e2_tsi,22,500).
cost(e2_tti,22,500).
cost(k1_p1,32,1000).
cost(m1_pv,22,500).
cost(m2_pv,100,10000).
cost(m3_pv,32,1000).
cost(r1_t2,22,500).
cost(snk1_p,32,1000).
cost(snk1_t,22,500).
cost(snk1_z_c2h4o,224,50000).
cost(snk1_z_c2h4,224,50000).
cost(snk1_z_co2,224,50000).

1 { chosen(S,C) : cost(S,C,_) }.

% need to have these because they are used by the control loops
:- not chosen(m1_pv,_).
:- not chosen(m2_pv,_).

sqrt_cost(Sum) :- Sum = #sum { C, S : chosen(S,C) }.
tot_cost(Sum) :- Sum = #sum { CF, S : chosen(S,C), cost(S,C,CF) }.
n_chosen(N) :- N = #count { S : chosen(S,_) }.

% up to 5 sensors, up to 1 expensive sensor, up to 350 summed square root cost
:- sqrt_cost(C), C > 350.
:- n_chosen(N), N > 5.
:- N = #count { S : chosen(S,C), C > 100 }, N > 1.

#show n_chosen/1.
#show chosen/2.
#show tot_cost/1.

