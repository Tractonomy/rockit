from casadi import *
from rockit import *

# Two-link system see two_link.png
# There is a geometric path given yd(s)
# We seek to traverse the path exactly, as fast as possible (torque limited)
# We start from a certain speed

# Transformation given on p14-16 in "Optimal Robot Path Following", PhD thesis, Frederik Debrouwere https://lirias.kuleuven.be/retrieve/336410
# 

#Define kinematic parameters
l1 = 1 #length
l2 = 1
m1 = 1 #mass
m2 = 2
I1 = 0.5 #inertia around COG
I2 = 0.5
lc1 = 0.5#COG
lc2 = 0.5

grav = 9.81 #gravitational constant

#Define dynamic parameters
mu11 = m1
mu21 = m1*lc1
mu31 = m1*lc1**2+I1

mu12 = m2
mu22 = m2*lc2
mu32 = m2*lc2**2+I2

#Torque limits
τ_lim = vertcat(30,15)

#Define matrices describing robot dynamics as functions
M = lambda q: blockcat([[mu12*l1**2+mu22*2*l1*cos(q[1])+mu31+mu32,mu32+mu22*l1*cos(q[1])],
          [mu32+mu22*l1*cos(q[1]),mu32]])
      
# NOTE: C is always linear in joint velocities (Verscheure)
# NOTE: "C(q,q̇) * q̇" notation hides structure. This term is really a pure quadratic in q̇ (no linear or constant part, barring time-varying mass)   https://www.tu-chemnitz.de/informatik/KI/edu/robotik/ws2017/Dyn.pdf
# NOTE: einstein notatoin: Cijk(q) q̇j q̇k
C = lambda q,q̇: blockcat([[-mu22*l1*sin(q[1])*q̇[1],-mu22*l1*sin(q[1])*(q̇[0]+q̇[1])],
            [mu22*l1*sin(q[1])*q̇[0],0]])
        
G = lambda q: grav*vertcat(mu12*l1*cos(q[0])+mu21*cos(q[0])+mu22*cos(q[0]+q[1]),mu22*cos(q[0]+q[1]))

#Define matrix describing robot kinematics
chi = lambda q: vertcat(l1*cos(q[0])+l2*cos(q[0]+q[1]),l1*sin(q[0])+l2*sin(q[0]+q[1]))

# Inverse kinematics: chi_inv(chi(q0)) == q0
def chi_inv(y):
    c = (y[0]**2+y[1]**2-l1**2-l2**2)/(2*l1*l2)
    q2 = acos(c)
    q1 = atan2(y[1],y[0])-atan2(l2*sin(q2),l1+l2*c)
    return vertcat(q1,q2)

#Define desired trajectory of the end-effector in Cartesian space
L = 1 # s in [0,L]
yd = lambda s : vertcat(1.5,0)*s/L+vertcat(0,1.5)*(1-s/L) #straight line as a function of s

qd = lambda s: chi_inv(yd(s))

T0 = 1
# Start speed
v0 = 1 # [m/s]

# Independent variable is s
ocp = Ocp(T=L)

s = ocp.t

b = ocp.state() # b(s) = ṡ^2
a = ocp.control() # a(s) = s̈
ocp.set_der(b, 2*a)

# No going back along the path - b(s) = ṡ^2
ocp.subject_to(b>=0)

T = ocp.integral(1/sqrt(b))
# Minimize time
ocp.add_objective(T)

q = qd(s)
q_ds = ocp.der(q)     # w.r.t. s
q_dds = ocp.der(q_ds) # w.r.t. s

# q̈(s) = q''(s) ṡ^2 + q'(s) s̈
q̈ = q_dds*b+q_ds*a

# Q: how to write q̇ as a convex relation of a and b?
# A: impossible
# Q: but what do we do with C(q,q̇) then? How to write it in terms of a and b?
# A: impossible
# Q: so no coriolis for us?
# A: it's perfectly possible to write the full coriolis contribution c(q,q̇)== C(q,q̇) q̇
#    in terms of b: c(q,q̇) is really quadratic in vector q̇: Cijk(q) q̇j q̇k
#    we just use q' instead of q̇ and do a scalar scaling with ṡ^2
c = (C(q,q_ds) @ q_ds)*b

τ = M(q) @ q̈ + c + G(q)

# Torque constraints
ocp.subject_to(-τ_lim <= (τ <= τ_lim))

v_squared = sumsqr(ocp.der(yd(s)))*b

# Start from a given initial speed
ocp.subject_to(ocp.at_t0(v_squared)==v0**2)

# Invent some initial guesses
ocp.set_initial(a, 0)
ocp.set_initial(b, (L/T0)**2)

ocp.method(MultipleShooting(N=100))

ocp.solver("ipopt",{"expand":True})

sol = ocp.solve()

# N=100:  Transit time [s]:  0.8279471623786231 (14 iters, 0.017 s)
# N=1000: Transit time [s]:  0.8330111227858171 (18 iters, 0.182 s)
# N=5000: Transit time [s]:  0.8335942348531639 (18 iters, 0.932 s)
print("Transit time [s]: ", sol.value(T))

# Post processing

import pylab as plt

plt.figure()
plt.plot(*sol.sample(a,grid='integrator',refine=10))
plt.plot(*sol.sample(b,grid='integrator',refine=10))
plt.plot(*sol.sample(1/sqrt(b),grid='integrator',refine=10))
plt.grid(True)
plt.xlabel("Time [s]")
plt.title("a b")


plt.figure()
plt.plot(*sol.sample(τ,grid='integrator',refine=10))
plt.grid(True)
plt.xlabel("Time [s]")
plt.title("control effort (torques)")


plt.figure()
plt.plot(*sol.sample(q,grid='integrator',refine=10))
plt.grid(True)
plt.xlabel("Time [s]")
plt.title("joint evolution")

plt.figure()


[_,chi_sol] = sol.sample(chi(q),grid='control')
[_,chi_sol_fine] = sol.sample(chi(q),grid='control')
plt.plot(chi_sol[:,0],chi_sol[:,1],'bo')
plt.plot(chi_sol_fine[:,0],chi_sol[:,1],'b')

plt.xlabel("x position [m]")
plt.ylabel("y position [m]")

plt.title("Geometric plot")


plt.show()


