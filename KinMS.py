# coding: utf-8
"""
Copyright (C) 2016, Timothy A. Davis
E-mail: DavisT -at- cardiff.ac.uk

Updated versions of the software are available through github:
https://github.com/TimothyADavis/KinMSpy

If you have found this software useful for your research,
I would appreciate an acknowledgment to the use of the
"KINematic Molecular Simulation (KinMS) routines of Davis et al., (2013)".
[MNRAS, Volume 429, Issue 1, p.534-555]

This software is provided as is without any warranty whatsoever.
For details of permissions granted please see LICENCE.md
"""

import numpy as np
import scipy.integrate
from scipy import interpolate
from astropy.io import fits
from astropy.convolution import convolve_fft

class KinMS:

    def __init__(self):

        self.verbose = True # SET TO FALSE WHEN FINISHED
        self.diskThick = 0
        self.nSamps = int(5e5)
        self.fixedSeed = np.array([100, 101, 102, 103])
        self.randomSeed = np.random.randint(0, 100, 4)
        self.vRadial = 0
        self.vPhaseCent = [0, 0]
        self.posAng_rad = 0
        self.inc_rad = 0

        if self.verbose:
            print("\n *** Hello and welcome to the grand KinMSpy :D *** \n ")

    def print_variables(self, param_dict):

        print('_' * 37 + '\n \n' + 'Setting values to: \n ')
        for k in param_dict:
            print(k + ' = ' + str(param_dict[k]))
        print('_' * 37)
        return

    def makebeam(self, xpixels, ypixels, beamSize, cellSize=1, cent=None):
        """
        :param xpixels: Number of pixels in the x-axis
        :param ypixels: Number of pixels in the y-axis
        :param beamSize: Beam information. This can be a list/numpy array of length 2 or 3: the first two elements
                         contain the sizes of the major and minor axes (the order does not matter) in arcseconds (RIGHT??),
                         the third element is the position angle. If no third element is given, the angle is assumed to
                         be zero. If an integer/float is given, a circular beam of that size is assumed.
        :param cellSize:
        :param cent:
        :return:
        """

        if not cent: cent = [xpixels / 2, ypixels / 2]

        beamSize = np.array(beamSize)

        try:
            if len(beamSize) == 2:
                beamSize = np.append(beamSize, 0)
            if beamSize[1] > beamSize[0]:
                beamSize[1], beamSize[0] = beamSize[0], beamSize[1]
        except:
            beamSize = np.array([beamSize, beamSize, 0])

        st_dev = beamSize[0:2] / cellSize / 2.355

        rot = beamSize[2]

        if np.tan(np.radians(rot)) == 0:
            dirfac = 1
        else:
            dirfac = np.sign(np.tan(np.radians(rot)))

        x, y = np.indices((int(xpixels), int(ypixels)), dtype='float')

        x -= cent[0]
        y -= cent[1]

        a = (np.cos(np.radians(rot)) ** 2) / (2 * st_dev[1] ** 2) + (np.sin(np.radians(rot)) ** 2) / \
            (2 * (st_dev[0] ** 2))

        b = (dirfac * (np.sin(2 * np.radians(rot)) ** 2) / (4 * st_dev[1] ** 2)) + ((-1 * dirfac) * \
            (np.sin(2 * np.radians(rot)) ** 2) / (4 * st_dev[0] ** 2))

        c = (np.sin(np.radians(rot)) ** 2) / (2 * st_dev[1] ** 2) + (np.cos(np.radians(rot)) ** 2) / \
            (2 * st_dev[0] ** 2)

        psf = np.exp(-1 * (a * x ** 2 - 2 * b * (x * y) + c * y ** 2))

        return psf

    def kinms_sampleFromArbDist_oneSided(self, sbRad, sbProf, fixSeed, nSamps, diskThick=None):
        """

        This function takes the input radial distribution and generates the positions of
        "nSamps" cloudlets from under it. It also accounts for disk thickness if requested.

        Parameters
        ----------
        sbRad : np.ndarray or list of floats
                Radius vector (in units of pixels).

        sbProf : np.ndarray or list of floats
                Surface brightness profile (arbitrarily scaled).

        nSamps : int
                Number of samples to draw from the distribution (default is 5e5).

        fixSeed : bool
                Whether to use a fixed (or random) seed (list of four integers).

        diskThick : float or np.ndarray/list of floats
             (Default value = 0.0)
             The disc scaleheight. If a single value then this is used at all radii.
             If a list/ndarray then it should have the same length as sbRad, and will be
             the disc thickness as a function of sbRad.

        Returns
        -------
        inClouds : np.ndarray of floats
                Returns an ndarray of "nSamps" by 3 in size. Each row corresponds to the x, y, z position of a cloudlet.
        """

        if self.verbose: print('Generating cloudlets,', end=' ')

        # If variables are not entered by user, adopt default (global) values.
        if fixSeed:
            seed = self.fixedSeed
        else:
            seed = self.randomSeed

        if nSamps:
            nSamps = int(nSamps)
        else:
            nSamps = self.nSamps

        if not diskThick:
            diskThick = self.diskThick

        # Set everything to numpy arrays to accept list input
        sbRad = np.array(sbRad)
        sbProf = np.array(sbProf)

        # Randomly generate the radii of clouds based on the distribution given by the brightness profile.
        px = scipy.integrate.cumtrapz(sbProf * 2 * np.pi * abs(sbRad), abs(sbRad), initial=0)
        px /= max(px)
        rng1 = np.random.RandomState(seed[0])
        pick = rng1.random_sample(nSamps)
        interpfunc = interpolate.interp1d(px, sbRad, kind='linear')
        r_flat = interpfunc(pick)

        # Generates a random phase around the galaxy's axis for each cloud.
        rng2 = np.random.RandomState(seed[1])
        phi = rng2.random_sample(nSamps) * 2 * np.pi

        # Find the thickness of the disk at the radius of each cloud.
        try:
            if len(diskThick) != len(sbRad):
                print('\n \n ... Please make sure the length of diskThick is the same as that of sbRad! Returning.')
                return

            if self.verbose: print('using the scale height profile provided.')
            diskThick = np.array(diskThick)
            interpfunc2 = interpolate.interp1d(sbRad, diskThick, kind='linear')
            diskThick_here = interpfunc2(r_flat)

        except:
            diskThick_here = diskThick
            if self.verbose: print('using a constant scale height of ' + str(diskThick) + '.')

        # Generates a random (uniform) z-position satisfying |z|<disk_here.
        rng3 = np.random.RandomState(seed[3])
        zPos = diskThick_here * rng3.uniform(-1, 1, nSamps)

        # Calculate the x & y position of the clouds in the x-y plane of the disk.
        r_3d = np.sqrt((r_flat ** 2) + (zPos ** 2))
        theta = np.arccos(zPos / r_3d)
        xPos = ((r_3d * np.cos(phi) * np.sin(theta)))
        yPos = ((r_3d * np.sin(phi) * np.sin(theta)))

        # Generates the output array
        inClouds = np.vstack((xPos, yPos, zPos)).T

        return inClouds
    
    def kinms_create_velField_oneSided(self, velRad, velProf, r_flat, inc, posAng, gasSigma, xPos, yPos, fixSeed=None, 
                                       vPhaseCent=None, vRadial=None, posAng_rad=None, inc_rad=None, vPosAng=False):
            

        """
        
        This function takes the input circular velocity distribution
        and the position of point sources and creates the velocity field
        taking into account warps, inflow/outflow etc as required.
        
        Parameters
        ----------
        velRad : np.ndarray of double
                Radius vector (in units of pixels).
        
        velProf : np.ndarray of double
                Velocity profile (in units of km/s).
        
        r_flat : np.ndarray of double
                Radius of each cloudlet from the kinematic centre
                in the plane of the disc. Units of pixels.
        
        inc : double or np.ndarray of double
                Inclination of the disc, using the usual astronomical convention.
                Can be either a double, or an array of doubles. If single valued
                then the disc is flat. If an array is passed then it should
                describe how the galaxy inclination changes as a function of `velrad`.
                Used to create inclination warps.
        
        posAng : double or np.ndarray of double
                Position angle of the disc, using the usual astronomical convention.
                Can be either a double, or an array of doubles. If single valued
                then the disc major axis is straight. If an array is passed then it should
                describe how the position angle changes as a function of `velrad`.
                Used to create position angle warps.
        
        gasSigma : double or np.ndarray of double
                Velocity dispersion of the gas. Units of km/s.
                Can be either a double, or an array of doubles. If single valued
                then the velocity dispersion is constant throughout the disc.
                If an array is passed then it should describe how the velocity
                dispersion changes as a function of `velrad`.
        
        fixSeed : list of int
                List of length 4 containing the seeds for random number generation.
        
        xPos : np.ndarray of double
                X position of each cloudlet. Units of pixels.
                
        Pos : np.ndarray of double
                Y position of each cloudlet. Units of pixels.
        
        vPhaseCent : list of double
             (Default value = [0, 0])
                Kinematic centre of the rotation in the x-y plane. Units of pixels.
                Used if the kinematic and morphological centres are not the same.
        
        vPosAng : double or np.ndarray of double
             (Default value = False)
                Kinematic position angle of the disc, using the usual astronomical convention.
                Can be either a double, or an array of doubles. If single valued
                then the disc kinematic major axis is straight. If an array is passed then it should
                describe how the kinematic position angle changes as a function of `velrad`.
                Used if the kinematic and morphological position angles are not the same.
        
        vRadial : double or np.ndarray of double
             (Default value = 0)
                Magnitude of inflow/outflowing motions (km/s). Negative
                numbers here are inflow, positive numbers denote
                outflow. These are included in the velocity field using
                formalism of KINEMETRY (Krajnović et al. 2006 MNRAS, 366, 787).
                Can input a constant or a vector, giving the radial
                motion as a function of the radius vector
                `velrad`. Default is no inflow/outflow.
        
        posAng_rad : double or np.ndarray of double
             (Default value = 0)
                Position angle of the disc at the position `r_flat` of each cloudlet.
        
        inc_rad : double or np.ndarray of double
             (Default value = 0)
                Inclination angle of the disc at the position `r_flat` of each cloudlet.
        
        Returns
        -------
        los_vel : np.ndarray of double
                Line of sight velocity of each cloudlet, in km/s.
        
        """
        
        if fixSeed:
            seed = self.fixedSeed
        else:
            seed = self.randomSeed
                    
        if vPhaseCent:
                vPhaseCent = vPhaseCent
        else:
                vPhaseCent = self.vPhaseCent
                
        if vRadial:
                vRadial = vRadial
        else:
                vRadial = self.vRadial
                    
        if posAng_rad:
                posAng_rad = posAng_rad
        else:
                posAng_rad = self.posAng_rad
                    
        if inc_rad:
                inc_rad = inc_rad
        else:
                inc_rad = self.inc_rad
                
        ### THIS PRINTING OF VARIABLES FROM A COLLECTION DICTIONARY STILL EXISTS
        ### BUT UNSURE IF WE'RE GOING TO KEEP THIS OR JUST PRINT AN AGGREGATED
        ### VERSION FROM THE INNIT FILE? 
                    
        parameter_dictionary = {}
        parameter_dictionary['vRadial'] = vRadial
        parameter_dictionary['vPhaseCent'] = vPhaseCent
        parameter_dictionary['posAng_rad'] = posAng_rad
        parameter_dictionary['inc_rad'] = inc_rad  
        self.print_variables(parameter_dictionary)
                  
        velInterFunc = interpolate.interp1d(velRad,velProf,kind='linear')
        vRad = velInterFunc(r_flat)
        # Calculate a peculiar velocity for each cloudlet based on the velocity dispersion
        rng4 = np.random.RandomState(seed[3]) 
        velDisp = rng4.randn(len(xPos))
        try:
                len(gasSigma)>1
                gasSigmaInterFunc = interpolate.interp1d(velRad,gasSigma,kind='linear')
                velDisp *= gasSigmaInterFunc(r_flat)
        except:
                velDisp *= gasSigma
                
        # Find the rotation angle so the velocity field has the correct position angle (allows warps)
        if not vPosAng:
            ang2rot=0
        else:
            try:
                len(vPosAng)>1
                vPosAngInterFunc = interpolate.interp1d(velRad,vPosAng,kind='linear')
                vPosAng_rad = vPosAngInterFunc(r_flat)
            except:
                vPosAng_rad = np.full(len(r_flat),vPosAng,np.double)
                ang2rot = ((posAng_rad-vPosAng_rad))
        #Calculate the los velocity for each cloudlet
        los_vel = velDisp                                                                                                                    
        los_vel += (-1) * vRad * (np.cos(np.arctan2((yPos + vPhaseCent[1]),(xPos + vPhaseCent[0])) + (np.radians(ang2rot))) * np.sin(np.radians(inc_rad)))
        #Add radial inflow/outflow
        try:
            len(vRadial)>1
            vRadialInterFunc = interpolate.interp1d(velRad,vRadial,kind='linear')
            vRadial_rad = vRadialInterFunc(r_flat)
        except:
            vRadial_rad=np.full(len(r_flat),vRadial,np.double)
        los_vel += vRadial_rad * (np.sin(np.arctan2((yPos+vPhaseCent[1]),(xPos + vPhaseCent[0])) + (np.radians(ang2rot))) * np.sin(np.radians(inc_rad)))
        # Output the array of los velocities
        return los_vel

    def save_fits(self, fileName, cube, cellSize, dv, cent, ra, dec, vSys, beamSize):

        hdu = fits.PrimaryHDU(cube.T)

        hdu.header['CDELT1'] = cellSize / -3600
        hdu.header['CDELT2'] = cellSize / 3600
        hdu.header['CDELT3'] = dv * 1000
        hdu.header['CRPIX1'] = cent[0] - 1
        hdu.header['CRPIX2'] = cent[1] - 1
        hdu.header['CRPIX3'] = cent[2]
        hdu.header['CRVAL1'] = ra
        hdu.header['CRVAL2'] = dec
        hdu.header['CRVAL3'] = vSys * 1000, 'm/s'
        hdu.header['CUNIT1'] = 'deg'
        hdu.header['CUNIT2'] = 'deg'
        hdu.header['CUNIT3'] = 'm/s'
        hdu.header['BSCALE'] = 1
        hdu.header['BZERO'] = 0
        hdu.header['BMIN'] = np.min(np.array(beamSize[0:2]) / 3600)
        hdu.header['BMAJ'] = np.max(np.array(beamSize[0:2]) / 3600)
        hdu.header['BTYPE'] = 'Intensity'
        hdu.header['BPA'] = beamSize[2]
        hdu.header['CTYPE1'] = 'RA---SIN'
        hdu.header['CTYPE2'] = 'DEC--SIN'
        hdu.header['CTYPE3'] = 'VRAD'
        hdu.header['EQUINOX'] = 2000
        hdu.header['RADESYS'] = 'FK5'
        hdu.header['BUNIT'] = 'Jy/beam'
        hdu.header['SPECSYS'] = 'BARYCENT'

        hdu.writeto(fileName + '_simcube.fits', overwrite=True, output_verify='fix')

        return

    def model_cube(self, xs, ys, vs, cellSize, dv, beamSize, inc, gasSigma=0, sbProf=[], sbRad=[], velRad=[], velProf=[],
                   diskThick=0, ra=0, dec=0, nSamps=None, posAng=0.0, intFlux=0,
                   inClouds=[], vLOS_clouds=[], flux_clouds=0, vSys=0, restFreq=115.271e9, phaseCen=np.array([0., 0.]),
                   vOffset=0, vRadial=0, vPosAng=0, vPhaseCen=np.array([0., 0.]), fileName=False, fixSeed=False,
                   cleanOut=False, returnClouds=False, gasGrav=False, verbose=False):
        """

        The main KinMS function. Takes inputs specifing the observing parameters and type of model.
        Returns the created model cube.

        Parameters
        ----------
        xs : float
            X-axis size for resultant cube (in arcseconds)

        ys : float
            Y-axis size for resultant cube (in arcseconds)

        vs : float
            Velocity axis size for resultant cube (in km/s)

        cellsize : float
            Pixel size required (arcsec/pixel)

        dv : float
            Channel size in velocity direction (km/s/channel)

        beamsize : float or list of float
            Scalar or three element list for size of convolving
            beam (in arcseconds).  If a scalar then beam is assumed
            to be circular. If a vector then denotes beam major
            axis size in element zero, and the beam minor axis in
            element one. The beam position angle should be given in
            element two. I.e. [bmaj,bmin,bpa].

        inc :   double or np.ndarray of double
            Inclination angle of the gas disc on the sky
            (degrees). Can input a constant or a vector,
            giving the inclination as a function of the
            radius vector `velrad` (in order to model warps etc)

        gassigma : double or np.ndarray of double, optional
             (Default value = 0)
            Velocity dispersion of the gas. Units of km/s.
            Can be either a double, or an array of doubles. If single valued
            then the velocity dispersion is constant throughout the disc.
            If an array is passed then it should describe how the velocity
            dispersion changes as a function of `velrad`.

        sbprof : np.ndarray of double, optional
             (Default value = [])
            Surface brightness profile (arbitrarily scaled) as a function of `sbrad`.

        sbrad : np.ndarray of double, optional
             (Default value = [])
            Radius vector for surface brightness profile (units of arcseconds).

        velrad : np.ndarray of double, optional
             (Default value = [])
            Radius vector for velocity profile (units of arcseconds).

        velprof : np.ndarray of double, optional
             (Default value = [])
            Circular velocity profile (in km/s) as a function of `velrad`.

        diskthick : double or np.ndarray of double, optional
             (Default value = 0)
            The disc scaleheight in arcseconds. If a single value then this is used at all radii.
            If a ndarray then it should have the same length as `sbrad`, and will be
            the disc thickness as a function of `sbrad`.

        cleanout : bool, optional
             (Default value = False)
            If set then do not convolve with the beam, and output the
            "clean components". Useful to create input for other
            simulation tools (e.g sim_observe in CASA).

        nsamps : int, optional
             (Default value = 100000)
            Number of cloudlets to use to create the model. Large numbers
            will reduce numerical noise (especially in large cubes),
            at the cost of increasing runtime.

        posang : double or np.ndarray of double, optional
             (Default value = 0.0)
            Position angle of the disc, using the usual astronomical convention.
            Can be either a double, or an array of doubles. If single valued
            then the disc major axis is straight. If an array is passed then it should
            describe how the position angle changes as a function of `velrad`.
            Used to create position angle warps.

        intflux : double, optional
             (Default value = 0)
            Total integrated flux you want the output gas to
            have. (In Jy/km/s).

        inclouds : np.ndarray of double, optional
             (Default value = [])
            If your required gas distribution is not symmetric you
            may input vectors containing the position of the
            clouds you wish to simulate. This 3-vector should
            contain the X, Y and Z positions, in units of arcseconds
            from the phase centre. If this variable is used, then
            `diskthick`, `sbrad` and `sbprof` are ignored.
            Example: INCLOUDS=[[0,0,0],[10,-10,2],...,[xpos,ypos,zpos]]

        vlos_clouds : np.ndarray of double, optional
             (Default value = [])
            This vector should contain the LOS velocity for
            each point defined in INCLOUDS, in units of km/s. If
            not supplied then INCLOUDS is assumed to be the -face
            on- distribution and that VELPROF/VELRAD should be
            used, and the distribution projected. If this
            variable is used then GASSIGMA/INC are ignored.

        flux_clouds : np.ndarray of double, optional
             (Default value = 0)
            This vector can be used to supply the flux of each
            point in INCLOUDS. If used alone then total flux in the model is equal
            to total(FLUX_INCLOUDS). If INTFLUX used then this vector denotes
            the relative brightness of the points in
            INCLOUDS.


        phasecen : np.ndarray of double, optional
             (Default value = np.array([0., 0.])
            This two dimensional array specifies the morphological centre of the
            disc structure you create with respect to the central pixel of the
            generated cube.

        returnclouds: bool, optional
            (Default value= False)
            If set True then KinMS returns the created `inclouds` and `vlos_clouds`
            in addition to the cube.

        Other Parameters
        ----------------

        filename : string or bool, optional
             (Default value = False)
            If you wish to save the resulting model to a fits file, set this variable.
            The output filename will be `filename`_simcube.fits

        ra : float, optional
             (Default value = 0)
            RA to use in the header of the output cube (in degrees).

        dec : float, optional
             (Default value = 0)
            DEC to use in the header of the output cube (in degrees).

        restfreq : double, optional
             (Default value = 115.271e9)
            Rest-frequency of spectral line of choice (in Hz). Only
            matters if you are outputting a FITS file  Default: 12CO(1-0)

        vsys : double, optional
             (Default value = 0)
            Systemic velocity (km/s).

        Returns
        -------

        cube : np.ndarray of double
            Returns the created cube as a 3 dimensional array

        inclouds: np.ndarray of double
            If `returnclouds` is set then this is returned, containing
            the cloudlets generated by KinMS

        vlos_clouds: np.ndarray of double
            If `returnclouds` is set then this is returned, containing
            the LOS velocities of cloudlets generated by KinMS

        """

        #nSamps = int(nSamps)

        # Generate seeds for use in future calculations
        #if fixSeed:
        #    fixSeed = [100, 101, 102, 103]
        #else:
        #    fixSeed = np.random.randint(0, 100, 4)

        if verbose: self.verbose = True

        # Work out images sizes
        xSize = np.round(xs / cellSize)
        ySize = np.round(ys / cellSize)
        vSize = np.round(vs / dv)

        cent = [(xSize / 2) + (phaseCen[0] / cellSize), (ySize / 2) + (phaseCen[1] / cellSize),
                (vSize / 2) + (vOffset / dv)]

        vPhaseCent = vPhaseCen / [cellSize, cellSize]

        # If cloudlets not previously specified, generate them
        if not len(inClouds):
            inClouds = self.kinms_sampleFromArbDist_oneSided(sbRad, sbProf, nSamps, fixSeed, diskThick=diskThick)

        xPos = (inClouds[:, 0] / cellSize); yPos = (inClouds[:, 1] / cellSize); zPos = (inClouds[:, 2] / cellSize)

        r_flat = np.sqrt((xPos * xPos) + (yPos * yPos))

        # Find the los velocity and cube position of the clouds
        if len(vLOS_clouds):
            # As los velocity specified assume that the clouds have already been projected correctly.
            los_vel = vLOS_clouds
            x2 = xPos
            y2 = yPos
            z2 = zPos

        else:
            # As los velocities not specified, calculate them
            if np.any(gasGrav):
                # ;;; include the potential of the gas
                gasGravVel = gasGravity_velocity(xPos * cellSize, yPos * cellSize, zPos * cellSize, gasGrav, velRad)
                velProf = np.sqrt((velProf * velProf) + (gasGravVel * gasGravVel))

            posAng = 90 - posAng
            if isinstance(posAng, (list, tuple, np.ndarray)):
                posAngRadInterFunc = interpolate.interp1d(velRad, posAng, kind='linear')
                posAng_rad = posAngRadInterFunc(r_flat * cellSize)
            else:
                posAng_rad = np.full(len(r_flat), posAng, np.double)

            if isinstance(inc, (list, tuple, np.ndarray)):
                incRadInterFunc = interpolate.interp1d(velRad, inc, kind='linear')
                inc_rad = incRadInterFunc(r_flat * cellSize)
            else:
                inc_rad = np.full(len(r_flat), inc, np.double)

            # Calculate the los velocity
            los_vel =self. kinms_create_velField_oneSided(velRad / cellSize, velProf, r_flat, inc, posAng, gasSigma, fixSeed,
                                                          xPos, yPos, vPhaseCent=vPhaseCent, vPosAng=vPosAng,
                                                          vRadial=vRadial, inc_rad=inc_rad, posAng_rad=posAng_rad)

            # Project the clouds to take into account inclination
            c = np.cos(np.radians(inc_rad))
            s = np.sin(np.radians(inc_rad))
            x2 = xPos
            y2 = (c * yPos) + (s * zPos)
            z2 = (-s * yPos) + (c * zPos)

            # Correct orientation by rotating by position angle
            ang = posAng_rad
            c = np.cos(np.radians(ang))
            s = np.sin(np.radians(ang))
            x3 = (c * x2) + (s * y2)
            y3 = (-s * x2) + (c * y2)
            x2 = x3
            y2 = y3

        # now add the flux into the cube
        # Centre the clouds in the cube on the centre of the object
        los_vel_dv_cent2 = np.round((los_vel / dv) + cent[2])
        x2_cent0 = np.round(x2 + cent[0])
        y2_cent1 = np.round(y2 + cent[1])

        # Find the reduced set of clouds that lie inside the cube
        subs = np.where(((x2_cent0 >= 0) & (x2_cent0 < xSize) & (y2_cent1 >= 0) & (y2_cent1 < ySize) & (
        los_vel_dv_cent2 >= 0) & (los_vel_dv_cent2 < vSize)))
        nsubs = subs[0].size
        clouds2do = np.empty((nsubs, 3))
        clouds2do[:, 0] = x2_cent0[subs]
        clouds2do[:, 1] = y2_cent1[subs]
        clouds2do[:, 2] = los_vel_dv_cent2[subs]

        # If there are clouds to use, and we know the flux of each cloud, add them to the cube. If not, bin each position to get
        # a relative flux
        if nsubs > 0:
            if not isinstance(flux_clouds, (list, tuple, np.ndarray)):
                cube, edges = np.histogramdd(clouds2do, bins=(xSize, ySize, vSize),
                                             range=((0, xSize), (0, ySize), (0, vSize)))
            else:
                cube = np.zeros((np.int(xSize), np.int(ySize), np.int(vSize)))
                flux_clouds = flux_clouds[subs]
                for i in range(0, nsubs):
                    const = flux_clouds[i]
                    csub = (int(clouds2do[i, 0]), int(clouds2do[i, 1]), int(clouds2do[i, 2]))
                    cube[csub] = cube[csub] + const
        else:
            cube = np.zeros((np.int(xSize), np.int(ySize), np.int(vSize)))

        # Convolve with the beam point spread function to obtain a dirty cube
        if not cleanOut:
            psf = self.makebeam(xSize, ySize, beamSize)
            w2do = np.where(cube.sum(axis=0).sum(axis=0) > 0)[0]
            for i in range(0, w2do.size): cube[:, :, w2do[i]] = convolve_fft(cube[:, :, w2do[i]], psf)
        # Normalise by the known integrated flux
        if intFlux > 0:
            if not cleanOut:
                cube *= ((intFlux * psf.sum()) / (cube.sum() * dv))
            else:
                cube *= ((intFlux) / (cube.sum() * dv))
        else:
            if isinstance(flux_clouds, (list, tuple, np.ndarray)):
                cube *= (flux_clouds.sum() / cube.sum())
            else:
                cube /= cube.sum()

        # If appropriate, generate the FITS file header and save to disc
        if fileName:
            self.save_fits(fileName, cube, cellSize, dv, cent, ra, dec, vSys, beamSize)

        # Output the final cube
        if returnClouds:
            retClouds = np.empty((nSamps, 3))
            retClouds[:, 0] = x2 * cellSize
            retClouds[:, 1] = y2 * cellSize
            retClouds[:, 2] = z2 * cellSize
            return cube, retClouds, los_vel
        else:
            return cube


KinMS().kinms_create_velField_oneSided(velRad=np.array([0,1,2]),velProf=np.array([1,1,1]),r_flat=np.array([0,1,2]),
      inc=90,posAng=45,gasSigma=np.array([1,1,1]),xPos=np.array([0,1,2]),yPos=np.array([0,1,2]))



def gasGravity_velocity(xPos,yPos,zPos,massDist,velRad):
    """
    This function takes the position of the input cloudlets, and calculates the
    potential, and thus the increase in the circular velocity due to the gas mass itself.

    Parameters
    ----------
    xPos : np.ndarray of double
            X position of each cloudlet. Units of arcseconds.

    yPos : np.ndarray of double
            Y position of each cloudlet. Units of arcseconds.

    zPos : np.ndarray of double
            Z position of each cloudlet. Units of arcseconds

    massDist : list of double
            List of [gasmass,distance] - gas mass in solar masses, distance in Mpc.

    velRad : np.ndarray of double
            Radius vector (in units of pixels).

    Returns
    -------
    np.ndarray of double
            Addition to the circular velocity just due to the mass of the gas itself, in units of km/s.
    """
    rad = np.sqrt((xPos**2) + (yPos**2) + (zPos**2))						                            ## 3D radius
    cumMass = ((np.arange(xPos.size + 1)) * (massDist[0] / np.float(xPos.size)))					    ## cumulative mass
    cumMass_interFunc = interpolate.interp1d(np.append(np.insert(sorted(rad),0,0),np.max(velRad).clip(min=np.max(rad), max=None)+1),np.append(cumMass,np.max(cumMass)),kind='linear')
    if velRad[0] == 0.0:
        return 	np.append(0.0,np.sqrt((4.301e-3 * cumMass_interFunc(velRad[1:]))/(4.84 * velRad[1:] * massDist[1])))					    ## return velocity
    else:
        return 	np.sqrt((4.301e-3 * cumMass_interFunc(velrad))/(4.84 * velRad * massDist[1]))

def model_cube(xs,ys,vs,cellSize,dv,beamSize,inc,gasSigma=0,sbProf=[],sbRad=[],velRad=[],velProf=[],fileName=False,diskThick=0,cleanOut=False,ra=0,dec=0,nSamps=100000,posAng=0.0,intFlux=0,inClouds=[],vLOS_clouds=[],flux_clouds=0,vSys=0,restFreq=115.271e9,phaseCen=np.array([0.,0.]),vOffset=0,fixSeed=False,vRadial=0,vPosAng=0,vPhaseCen=np.array([0.,0.]),returnClouds=False,gasGrav=False):
    """

    The main KinMS function. Takes inputs specifing the observing parameters and type of model.
    Returns the created model cube.

    Parameters
    ----------
    xs : float
        X-axis size for resultant cube (in arcseconds)

    ys : float
        Y-axis size for resultant cube (in arcseconds)

    vs : float
        Velocity axis size for resultant cube (in km/s)

    cellsize : float
        Pixel size required (arcsec/pixel)

    dv : float
        Channel size in velocity direction (km/s/channel)

    beamsize : float or list of float
        Scalar or three element list for size of convolving
        beam (in arcseconds).  If a scalar then beam is assumed
        to be circular. If a vector then denotes beam major
        axis size in element zero, and the beam minor axis in
        element one. The beam position angle should be given in
        element two. I.e. [bmaj,bmin,bpa].

    inc :   double or np.ndarray of double
        Inclination angle of the gas disc on the sky
        (degrees). Can input a constant or a vector,
        giving the inclination as a function of the
        radius vector `velrad` (in order to model warps etc)

    gassigma : double or np.ndarray of double, optional
         (Default value = 0)
        Velocity dispersion of the gas. Units of km/s.
        Can be either a double, or an array of doubles. If single valued
        then the velocity dispersion is constant throughout the disc.
        If an array is passed then it should describe how the velocity
        dispersion changes as a function of `velrad`.

    sbprof : np.ndarray of double, optional
         (Default value = [])
        Surface brightness profile (arbitrarily scaled) as a function of `sbrad`.

    sbrad : np.ndarray of double, optional
         (Default value = [])
        Radius vector for surface brightness profile (units of arcseconds).

    velrad : np.ndarray of double, optional
         (Default value = [])
        Radius vector for velocity profile (units of arcseconds).

    velprof : np.ndarray of double, optional
         (Default value = [])
        Circular velocity profile (in km/s) as a function of `velrad`.

    diskthick : double or np.ndarray of double, optional
         (Default value = 0)
        The disc scaleheight in arcseconds. If a single value then this is used at all radii.
        If a ndarray then it should have the same length as `sbrad`, and will be
        the disc thickness as a function of `sbrad`.

    cleanout : bool, optional
         (Default value = False)
        If set then do not convolve with the beam, and output the
        "clean components". Useful to create input for other
        simulation tools (e.g sim_observe in CASA).

    nsamps : int, optional
         (Default value = 100000)
        Number of cloudlets to use to create the model. Large numbers
        will reduce numerical noise (especially in large cubes),
        at the cost of increasing runtime.

    posang : double or np.ndarray of double, optional
         (Default value = 0.0)
        Position angle of the disc, using the usual astronomical convention.
        Can be either a double, or an array of doubles. If single valued
        then the disc major axis is straight. If an array is passed then it should
        describe how the position angle changes as a function of `velrad`.
        Used to create position angle warps.

    intflux : double, optional
         (Default value = 0)
        Total integrated flux you want the output gas to
        have. (In Jy/km/s).

    inclouds : np.ndarray of double, optional
         (Default value = [])
        If your required gas distribution is not symmetric you
        may input vectors containing the position of the
        clouds you wish to simulate. This 3-vector should
        contain the X, Y and Z positions, in units of arcseconds
        from the phase centre. If this variable is used, then
        `diskthick`, `sbrad` and `sbprof` are ignored.
        Example: INCLOUDS=[[0,0,0],[10,-10,2],...,[xpos,ypos,zpos]]

    vlos_clouds : np.ndarray of double, optional
         (Default value = [])
        This vector should contain the LOS velocity for
        each point defined in INCLOUDS, in units of km/s. If
        not supplied then INCLOUDS is assumed to be the -face
        on- distribution and that VELPROF/VELRAD should be
        used, and the distribution projected. If this
        variable is used then GASSIGMA/INC are ignored.

    flux_clouds : np.ndarray of double, optional
         (Default value = 0)
        This vector can be used to supply the flux of each
        point in INCLOUDS. If used alone then total flux in the model is equal
        to total(FLUX_INCLOUDS). If INTFLUX used then this vector denotes
        the relative brightness of the points in
        INCLOUDS.


    phasecen : np.ndarray of double, optional
         (Default value = np.array([0., 0.])
        This two dimensional array specifies the morphological centre of the
        disc structure you create with respect to the central pixel of the
        generated cube.

    returnclouds: bool, optional
        (Default value= False)
        If set True then KinMS returns the created `inclouds` and `vlos_clouds`
        in addition to the cube.

    Other Parameters
    ----------------

    filename : string or bool, optional
         (Default value = False)
        If you wish to save the resulting model to a fits file, set this variable.
        The output filename will be `filename`_simcube.fits

    ra : float, optional
         (Default value = 0)
        RA to use in the header of the output cube (in degrees).

    dec : float, optional
         (Default value = 0)
        DEC to use in the header of the output cube (in degrees).

    restfreq : double, optional
         (Default value = 115.271e9)
        Rest-frequency of spectral line of choice (in Hz). Only
        matters if you are outputting a FITS file  Default: 12CO(1-0)

    vsys : double, optional
         (Default value = 0)
        Systemic velocity (km/s).

    Returns
    -------

    cube : np.ndarray of double
        Returns the created cube as a 3 dimensional array

    inclouds: np.ndarray of double
        If `returnclouds` is set then this is returned, containing
        the cloudlets generated by KinMS

    vlos_clouds: np.ndarray of double
        If `returnclouds` is set then this is returned, containing
        the LOS velocities of cloudlets generated by KinMS

    """


    nSamps = int(nSamps)
    # Generate seeds for use in future calculations
    if fixSeed:
        fixSeed = [100,101,102,103]
    else:
        fixSeed = np.random.randint(0,100,4)

    # If beam profile not fully specified, generate it:
    if not isinstance(beamSize, (list, tuple, np.ndarray)):
        beamSize = np.array([beamSize,beamSize,0])

    # work out images sizes
    xSize = float(round(xs/cellSize))
    ySize = float(round(ys/cellSize))
    vSize = float(round(vs/dv))
    cent = [(xSize/2.) + (phaseCen[0] / cellSize),(ySize / 2.) + (phaseCen[1] / cellSize),(vSize / 2.) + (vOffset / dv)]
    vPhaseCent = (vPhaseCen) / [cellSize,cellSize]

    #If cloudlets not previously specified, generate them
    if not len(inClouds):
        inClouds = kinms_sampleFromArbDist_oneSided(sbRad,sbProf,nSamps,fixSeed,diskThick=diskThick)
    xPos = (inClouds[:,0] / cellSize)
    yPos = (inClouds[:,1] / cellSize)
    zPos = (inClouds[:,2] / cellSize)
    r_flat = np.sqrt((xPos * xPos) + (yPos * yPos))

    #Find the los velocity and cube position of the clouds
    if len(vLOS_clouds):
        #As los velocity specified assume that the clouds have already been projected correctly.
        los_vel = vLOS_clouds
        x2 = xPos
        y2 = yPos
        z2 = zPos
    else:
        # As los velocities not specified, calculate them
        if np.any(gasGrav):
            # ;;; include the potential of the gas
            gasGravVel = gasGravity_velocity(xPos * cellSize,yPos * cellSize,zPos * cellSize,gasGrav,velRad)
            velProf = np.sqrt((velProf * velProf) + (gasGravVel * gasGravVel))



        posAng = 90 - posAng
        if isinstance(posAng, (list, tuple, np.ndarray)):
            posAngRadInterFunc = interpolate.interp1d(velRad,posAng,kind='linear')
            posAng_rad = posAngRadInterFunc(r_flat*cellSize)
        else:
            posAng_rad = np.full(len(r_flat),posAng,np.double)

        if isinstance(inc, (list, tuple, np.ndarray)):
            incRadInterFunc = interpolate.interp1d(velRad,inc,kind='linear')
            inc_rad = incRadInterFunc(r_flat*cellSize)
        else:
            inc_rad = np.full(len(r_flat),inc,np.double)

        # Calculate the los velocity
        los_vel = kinms_create_velField_oneSided(velRad / cellSize,velProf,r_flat,inc,posAng,gasSigma,fixSeed,xPos,yPos,vPhaseCent=vPhaseCent,vPosAng=vPosAng,vRadial=vRadial,inc_rad=inc_rad,posAng_rad=posAng_rad)

        # Project the clouds to take into account inclination
        c = np.cos(np.radians(inc_rad))
        s = np.sin(np.radians(inc_rad))
        x2 =  xPos
        y2 = (c * yPos) + (s * zPos)
        z2 = (-s * yPos) + (c * zPos)

        # Correct orientation by rotating by position angle
        ang = posAng_rad
        c = np.cos(np.radians(ang))
        s = np.sin(np.radians(ang))
        x3 = (c * x2) + (s * y2)
        y3 = (-s * x2) + (c * y2)
        x2 = x3
        y2 = y3
    # now add the flux into the cube
    # Centre the clouds in the cube on the centre of the object
    los_vel_dv_cent2 = np.round((los_vel / dv) + cent[2])
    x2_cent0 = np.round(x2 + cent[0])
    y2_cent1 = np.round(y2 + cent[1])

    #Find the reduced set of clouds that lie inside the cube
    subs = np.where(((x2_cent0 >= 0) & (x2_cent0 < xSize) & (y2_cent1 >= 0) & (y2_cent1 < ySize) & (los_vel_dv_cent2 >= 0) & (los_vel_dv_cent2 < vSize)))
    nsubs = subs[0].size
    clouds2do = np.empty((nsubs,3))
    clouds2do[:,0] = x2_cent0[subs]
    clouds2do[:,1] = y2_cent1[subs]
    clouds2do[:,2] = los_vel_dv_cent2[subs]

    # If there are clouds to use, and we know the flux of each cloud, add them to the cube. If not, bin each position to get
    # a relative flux
    if nsubs > 0:
        if not isinstance(flux_clouds, (list, tuple, np.ndarray)):
            cube,edges = np.histogramdd(clouds2do,bins=(xSize,ySize,vSize),range=((0,xSize),(0,ySize),(0,vSize)))
        else:
            cube = np.zeros((np.int(xSize),np.int(ySize),np.int(vSize)))
            flux_clouds = flux_clouds[subs]
            for i in range(0, nsubs):
                const = flux_clouds[i]
                csub = (int(clouds2do[i,0]),int(clouds2do[i,1]),int(clouds2do[i,2]))
                cube[csub] = cube[csub] + const
    else: cube = np.zeros((np.int(xSize),np.int(ySize),np.int(vSize)))

    # Convolve with the beam point spread function to obtain a dirty cube
    if not cleanOut:
       psf = makebeam(xSize,ySize,beamSize) # makebeam is now a function in the class so need to change!
       w2do = np.where(cube.sum(axis=0).sum(axis=0) >0)[0]
       for i in range(0,w2do.size): cube[:,:,w2do[i]] = convolve_fft(cube[:,:,w2do[i]], psf)
    # Normalise by the known integrated flux
    if intFlux > 0:
        if not cleanOut:
            cube *= ((intFlux * psf.sum()) / (cube.sum() * dv))
        else:
            cube *= ((intFlux) / (cube.sum() * dv))
    else:
        if isinstance(flux_clouds, (list, tuple, np.ndarray)):
            cube *= (flux_clouds.sum() / cube.sum())
        else:
            cube /= cube.sum()

    # If appropriate, generate the FITS file header and save to disc
    if fileName:
        hdu = fits.PrimaryHDU(cube.T)
        hdu.header['CDELT1'] = (cellSize)/(-3600.0)
        hdu.header['CDELT2'] = (cellSize)/3600.0
        hdu.header['CDELT3'] = (dv)*1000.0
        hdu.header['CRPIX1'] = (cent[0]-1)
        hdu.header['CRPIX2'] = (cent[1]-1)
        hdu.header['CRPIX3'] = (cent[2])
        hdu.header['CRVAL1'] = (ra)
        hdu.header['CRVAL2'] = (dec)
        hdu.header['CRVAL3'] = (vSys*1000.0),"m/s"
        hdu.header['CUNIT1'] = 'deg'
        hdu.header['CUNIT2'] = 'deg'
        hdu.header['CUNIT3'] = 'm/s'
        hdu.header['BSCALE'] = 1.0
        hdu.header['BZERO'] = 0.0
        hdu.header['BMIN'] = np.min(np.array(beamSize[0:1])/3600.0)
        hdu.header['BMAJ'] = np.max(np.array(beamSize[0:1])/3600.0)
        hdu.header['BTYPE'] = 'Intensity'
        hdu.header['BPA'] = beamSize[2]
        hdu.header['CTYPE1'] = 'RA---SIN'
        hdu.header['CTYPE2'] = 'DEC--SIN'
        hdu.header['CTYPE3'] = 'VRAD'
        hdu.header['EQUINOX'] = 2000.0
        hdu.header['RADESYS'] = 'FK5'
        hdu.header['BUNIT'] = 'Jy/beam'
        hdu.header['SPECSYS'] = 'BARYCENT'
        hdu.writeto(fileName+"_simcube.fits",overwrite=True,output_verify='fix')

    # Output the final cube
    if returnClouds:
        retClouds = np.empty((nSamps,3))
        retClouds[:,0] = x2 * cellSize
        retClouds[:,1] = y2 * cellSize
        retClouds[:,2] = z2 * cellSize
        return cube, retClouds, los_vel
    else:
        return cube