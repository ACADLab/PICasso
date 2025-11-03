import numpy as np

###############################
## DEVICE-LEVEL OPTIMIZATION ##
###############################

from s_optimize import DeviceOptimizer

S = ...  # the NxN complex scattering matrix
opt = DeviceOptimizer(S, input_ports=[0], output_ports=[3])  # example ports
res = opt.optimal_excitation()
print("max throughput:", float(res["eta_max"][0]))
print("min loss:", float(res["loss_min"][0]))
print("optimal input vector (full-port):", res["v_opt_in"])

###############################
## DEVICE-LEVEL OPTIMIZATION ##
###############################

from s_optimize import ScatteringNetwork

S1, S2 = ... , ...   # two devices' scattering matrices
net = ScatteringNetwork([S1, S2])

# wire some ports; use amp<1 to model link loss; trainable=True to tune phase
net.add_connection(p=3, q=0, amp=0.98, phi=0.0, trainable=True)
net.add_connection(p=5, q=2, amp=0.98, phi=0.0, trainable=True)

net.set_external_from_unconnected()
best = net.optimize_phases(src_port=0, target_ports=[7], w_reflect=0.0)
print("phi_opt:", best["phi_opt"])
print("throughput_to_target:", float(best["throughput_to_target"][0]))
print("internal_loss:", float(best["internal_loss"][0]))
