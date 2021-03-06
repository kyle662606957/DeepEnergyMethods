# -*- coding: utf-8 -*-
'''
Implements the the cube with hole benchmark problem
'''

import tensorflow as tf
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from pyevtk.hl import gridToVTK 

import scipy.io


import matplotlib as mpl
mpl.rcParams['figure.dpi'] = 200
import time
tf.reset_default_graph()   # To clear the defined variables and operations of the previous cell
np.random.seed(1234)
tf.set_random_seed(1234)

from utils.Geom import Geometry3D
from utils.PINN import Elasticity3D

class CubeWithHole(Geometry3D):
    '''
     Class for definining a quarter-annulus domain centered at the orgin
         (the domain is in the first quadrant)
     Input: rad_int, rad_ext - internal and external radii of the annulus
    '''
    def __init__(self):            
                
        geomData = dict()
        
        data = scipy.io.loadmat('cube_with_hole.mat')
        numCtrlPts = 5*5*2

        # Set degrees
        geomData['degree_u'] = data['vol1'][0][0][5][0][0] - 1
        geomData['degree_v'] = data['vol1'][0][0][5][0][1] - 1
        geomData['degree_w'] = data['vol1'][0][0][5][0][2] - 1
        
        # Set control points
        geomData['ctrlpts_size_u'] = np.int(data['vol1'][0][0][2][0][0])
        geomData['ctrlpts_size_v'] = np.int(data['vol1'][0][0][2][0][1])
        geomData['ctrlpts_size_w'] = np.int(data['vol1'][0][0][2][0][2])
        
        ctrlpts_x = data['vol1'][0][0][3][0,:].reshape(numCtrlPts, order='F')
        ctrlpts_y = data['vol1'][0][0][3][1,:].reshape(numCtrlPts, order='F')
        ctrlpts_z = data['vol1'][0][0][3][2,:].reshape(numCtrlPts, order='F')

        geomData['ctrlpts'] =  np.column_stack((ctrlpts_x, ctrlpts_y, ctrlpts_z))
        
        geomData['weights'] = data['vol1'][0][0][3][3,:].reshape(numCtrlPts, order='F')
        
        # Set knot vectors
        geomData['knotvector_u'] = [0., 0., 0., 0.5, 0.5, 1., 1., 1.]
        geomData['knotvector_v'] = [0., 0., 0., 0.5, 0.5, 1., 1., 1.]
        geomData['knotvector_w'] = [0., 0., 1., 1.]

        super().__init__(geomData)

class PINN_CWH(Elasticity3D):
    '''
    Class including (symmetry) boundary conditions for the hollow sphere problem
    '''       
    def net_uvw(self, x, y, z):

        X = tf.concat([x, y, z], 1)      

        uvw = self.neural_net(X, self.weights, self.biases)

        u = x*uvw[:, 0:1]
        v = y*uvw[:, 1:2]
        w = z*uvw[:, 2:3]

        return u, v, w

def cart2sph(x, y, z):
    # From https://stackoverflow.com/questions/30084174/efficient-matlab-cart2sph-and-sph2cart-functions-in-python
    azimuth = np.arctan2(y,x)
    elevation = np.arctan2(z,np.sqrt(x**2 + y**2))
    r = np.sqrt(x**2 + y**2 + z**2)
    return azimuth, elevation, r

def sph2cart(azimuth, elevation, r):
    # From https://stackoverflow.com/questions/30084174/efficient-matlab-cart2sph-and-sph2cart-functions-in-python
    x = r * np.cos(elevation) * np.cos(azimuth)
    y = r * np.cos(elevation) * np.sin(azimuth)
    z = r * np.sin(elevation)
    return x, y, z    

def getExactStresses(x, y, z, model):
    numPts = len(x)
    S = model['P']
    a = model['radInt']
    nu = model['nu']
    
    sigma_xx = np.zeros_like(x)
    sigma_yy = np.zeros_like(x)
    sigma_zz = np.zeros_like(x)
    sigma_xy = np.zeros_like(x)
    sigma_yz = np.zeros_like(x)
    sigma_zx = np.zeros_like(x)
    
    for i in range(numPts):
    
        azimuth, elevation, r  = cart2sph(x[i], y[i], z[i])    
        
        phi = azimuth
        theta = np.pi/2-elevation
        
        sigma_rr = S*np.cos(theta)*np.cos(theta)+S/(7-5*nu)*(a**3/r**3*(6-5*(5-nu)* \
                    np.cos(theta)*np.cos(theta))+(6*a**5)/r**5*(3*np.cos(theta)*np.cos(theta)-1))
        sigma_phiphi = 3*S/(2*(7-5*nu))*(a**3/r**3*(5*nu-2+5*(1-2*nu)*np.cos(theta)* \
                    np.cos(theta))+(a**5)/r**5*(1-5*np.cos(theta)*np.cos(theta)));
        sigma_thth =  S*np.sin(theta)*np.sin(theta)+S/(2*(7-5*nu))*(a**3/r**3* \
                    (4-5*nu+5*(1-2*nu)*np.cos(theta)*np.cos(theta))+(3*a**5)/r**5*\
                    (3-7*np.cos(theta)*np.cos(theta)))
        sigma_rth =  S*(-1+1/(7-5*nu)*(-5*a**3*(1+nu)/(r**3)+(12*a**5)/r**5))*np.sin(theta)*np.cos(theta)

        
        rot_mat = np.array( \
             [[np.sin(theta)*np.cos(phi), np.cos(theta)*np.cos(phi), -np.sin(phi)],
              [np.sin(theta)*np.sin(phi), np.cos(theta)*np.sin(phi), np.cos(phi)],
              [np.cos(theta), -np.sin(theta), 0.]])
        A = np.array( [[sigma_rr, sigma_rth, 0.], [sigma_rth, sigma_thth, 0.], [0., 0., sigma_phiphi]] )
        stress_cart = rot_mat@A@rot_mat.T
        
        sigma_xx[i] = stress_cart[0,0]
        sigma_yy[i] = stress_cart[1,1]
        sigma_zz[i] = stress_cart[2,2]
        sigma_xy[i] = stress_cart[0,1]
        sigma_zx[i] = stress_cart[0,2]
        sigma_yz[i] = stress_cart[1,2]    

    return sigma_xx, sigma_yy, sigma_zz, sigma_xy, sigma_yz, sigma_zx
    
model_data = dict()
model_data['E'] = 1e3
model_data['nu'] = 0.3

model = dict()
model['E'] = model_data['E']
model['nu'] = model_data['nu']
model['radInt'] = 1.
model['lenCube'] = 4.
model['P'] = 1.

# Domain bounds
model['lb'] = np.array([0., 0., 0.]) #lower bound of the plate
# Upper bound of the plate
model['ub'] = np.array([-model['lenCube'], model['lenCube'], model['lenCube']]) 

NN_param = dict()
NN_param['layers'] = [3, 30, 30, 30, 3]
NN_param['data_type'] = tf.float32

# Generating points inside the domain using GeometryIGA
myDomain = CubeWithHole()

#Load interior Gauss points
data = scipy.io.loadmat('gaussPtsCubeWithHole.mat')
X_f = data['gaussPts']

#Load boundary Gauss points, normals and tractions
dataBound = scipy.io.loadmat('gaussPtsBoundCubeWithHole.mat')
X_bnd = dataBound['gaussPtsBound']

fig = plt.figure(figsize=(6,6))
ax = fig.gca(projection='3d')
ax.scatter(X_f[:,0], X_f[:,1], X_f[:,2], s = 0.75)
ax.scatter(X_bnd[:,0], X_bnd[:,1], X_bnd[:,2], s=0.75)
ax.set_xlabel('$x$',fontweight='bold',fontsize = 12)
ax.set_ylabel('$y$',fontweight='bold',fontsize = 12)
ax.set_zlabel('$z$',fontweight='bold',fontsize = 12)
ax.tick_params(axis='both', which='major', labelsize = 6)
ax.tick_params(axis='both', which='minor', labelsize = 6)
plt.show()


model_pts = dict()
model_pts['X_int'] = X_f
model_pts['X_bnd'] = X_bnd

modelNN = PINN_CWH(model_data, model_pts, NN_param)

start_time = time.time()
num_train_its = 2000
modelNN.train(num_train_its)
elapsed = time.time() - start_time
print('Training time: %.4f' % (elapsed))

nPred = 50

withSides = [1, 1, 1, 1, 1, 1]
xGrid, yGrid, zGrid = myDomain.getUnifIntPts(nPred, nPred, nPred, withSides)
Grid = np.concatenate((xGrid, yGrid, zGrid), axis=1)

u_pred, v_pred, w_pred, energy_pred, sigma_x_pred, sigma_y_pred, sigma_z_pred, \
     sigma_xy_pred, sigma_yz_pred, sigma_zx_pred = modelNN.predict(Grid)

# Plot results        
oShapeX = np.resize(xGrid, [nPred, nPred, nPred])
oShapeY = np.resize(yGrid, [nPred, nPred, nPred])
oShapeZ = np.resize(zGrid, [nPred, nPred, nPred])

u = np.resize(u_pred, [nPred, nPred, nPred])
v = np.resize(v_pred, [nPred, nPred, nPred])
w = np.resize(w_pred, [nPred, nPred, nPred])
displacement = (u, v, w)

elas_energy = np.resize(energy_pred, [nPred, nPred, nPred])

gridToVTK("./CubeWithHole", oShapeX, oShapeY, oShapeZ, pointData = 
              {"Displacement": displacement, "Elastic Energy": elas_energy})

print('Loss convergence')    
range_adam = np.arange(1,num_train_its+1)
range_lbfgs = np.arange(num_train_its+2, num_train_its+2+len(modelNN.lbfgs_buffer))
ax0, = plt.plot(range_adam, modelNN.loss_adam_buff, label='Adam')
ax1, = plt.plot(range_lbfgs,  modelNN.lbfgs_buffer, label='L-BFGS')
plt.legend(handles=[ax0,ax1])
plt.ylim((min(modelNN.lbfgs_buffer),1))
plt.xlabel('Iteration')
plt.ylabel('Loss value')
plt.show()

#Compute the L2 and energy norm errors using integration
u_pred, v_pred, w_pred, energy_pred, sigma_x_pred, sigma_y_pred, sigma_z_pred, \
     tau_xy_pred, tau_yz_pred, tau_zx_pred = modelNN.predict(X_f)

sigma_xx_exact, sigma_yy_exact, sigma_zz_exact, sigma_xy_exact, sigma_yz_exact, \
    sigma_zx_exact = getExactStresses(X_f[:,0], X_f[:,1], X_f[:,2], model)
sigma_xx_err = sigma_xx_exact - sigma_x_pred[:,0]
sigma_yy_err = sigma_yy_exact - sigma_y_pred[:,0]
sigma_zz_err = sigma_zz_exact - sigma_z_pred[:,0]
sigma_xy_err = sigma_xy_exact - tau_xy_pred[:,0]
sigma_yz_err = sigma_yz_exact - tau_yz_pred[:,0]
sigma_zx_err = sigma_zx_exact - tau_zx_pred[:,0]

energy_err = 0
energy_norm = 0
numPts = X_f.shape[0]

C_mat = np.zeros((6,6))
C_mat[0,0] = model['E']*(1-model['nu'])/((1+model['nu'])*(1-2*model['nu']))
C_mat[1,1] = model['E']*(1-model['nu'])/((1+model['nu'])*(1-2*model['nu']))
C_mat[2,2] = model['E']*(1-model['nu'])/((1+model['nu'])*(1-2*model['nu']))
C_mat[0,1] = model['E']*model['nu']/((1+model['nu'])*(1-2*model['nu']))
C_mat[0,2] = model['E']*model['nu']/((1+model['nu'])*(1-2*model['nu']))
C_mat[1,0] = model['E']*model['nu']/((1+model['nu'])*(1-2*model['nu']))
C_mat[1,2] = model['E']*model['nu']/((1+model['nu'])*(1-2*model['nu']))
C_mat[2,0] = model['E']*model['nu']/((1+model['nu'])*(1-2*model['nu']))
C_mat[2,0] = model['E']*model['nu']/((1+model['nu'])*(1-2*model['nu']))
C_mat[3,3] = model['E']/(2*(1+model['nu']))
C_mat[4,4] = model['E']/(2*(1+model['nu']))
C_mat[5,5] = model['E']/(2*(1+model['nu']))

C_inv = np.linalg.inv(C_mat)
for i in range(numPts):
    err_pt = np.array([sigma_xx_err[i], sigma_yy_err[i], sigma_zz_err[i], 
                       sigma_xy_err[i], sigma_yz_err[i], sigma_zx_err[i]])
    norm_pt = np.array([sigma_xx_exact[i], sigma_yy_exact[i], sigma_zz_exact[i], \
                        sigma_xy_exact[i], sigma_yz_exact[i], sigma_zx_exact[i]])
    energy_err = energy_err + err_pt@C_inv@err_pt.T*X_f[i,3]
    energy_norm = energy_norm + norm_pt@C_inv@norm_pt.T*X_f[i,3]
    
print("Relative energy error (integration): ", np.sqrt(energy_err/energy_norm))
