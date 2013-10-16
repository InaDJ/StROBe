# -*- coding: utf-8 -*-
"""
Created on Mon October 07 16:16:10 2013

@author: Ruben Baetens
"""

import random
import numpy as np
import time
import stats
import datetime
import calendar
import ast
import os
import cPickle
import itertools

class Household(object):
    '''
    The Household class is the main class of ProclivityPy, defining the
    household composition as input or randomized based on statistics and
    allowing simulation of the household for building energy simulations.
    
    Main functions are:
        - __init__(), which ...
        - self.parameterize(), which ...
        - self.simulate(), which ...
    '''
    
    def __init__(self, name, **kwargs):
        '''
        Initiation of Househod object.
        '''
        # check on correct parameter input for use of functions as name should
        # be a string.
        try:
            if not isinstance(name, str):
                raise ValueError('Given name %d is not a string' % str(name))
        except:
            raise TypeError('give another name')
        # first define the name of the household object
        self.creation = time.asctime()
        self.name = name
        self.parameterize()

    def parameterize(self, **kwargs):
        '''
        Get a household definition for occupants and present appliances based
        on average statistics or the given kwargs.
        '''
        # get the occupant types
        def members(**kwargs):
            '''
            Define the employment type of all household members based on time
            use survey statistics or the given kwargs.
            '''
            members = []
            # First we check if membertypes are given as **kwargs
            if kwargs.has_key('members'):
                if isinstance(kwargs['members'], list):
                    members = kwargs['members']
                else:
                    raise TypeError('Given membertypes is no List of strings.')
            # If no types are given, random statististics are applied
            else:
                dataset = ast.literal_eval(open('Households.py').read())
                key = random.randint(0,len(dataset))
                members = dataset[key]
                print 'Household members employment are %s' % str(members)
            # And return the members as list fo strings
            return members
        # get the available appliances
        def appliances():
            '''
            Define the pressent household appliances based on average national
            statistics independent of household member composition.
            '''
            # Loop through all appliances and pick randomly based on the 
            # rate of ownership.
            dataset = ast.literal_eval(open('Appliances.py').read())
            app_n = []
            for app in dataset:
                obj = Equipment(**dataset[app])
                owner = obj.owner <= random.random()
                app_n.append(app) if owner else None
            return app_n            
        # and allocate the householdmembers to clusters
        def clusters(members):
            '''
            Allocate each household member to the correct cluster based on the 
            members occupation in time use survey data.
            '''
            clusters = []
            # loop for every individual in the household
            dataset = ast.literal_eval(open('Clusters.py').read())
            for ind in members:
                if ind != 'U12':
                    C = {}
                    # and loop for every type of day
                    for day in ['wkdy', 'sat', 'son']:
                        prob = dataset[day][ind]
                        cons = stats.get_probability(random.random(), 
                                                     prob, p_type='prob')+3
                        C.update({day : 'C'+str(cons)})
                    clusters.append(C)
            # and return the list of clusters
            return clusters
        # and run both
        self.members = members()
        self.apps = appliances()
        self.clusters = clusters(self.members)
        # and return
        return None

    def simulate(self, year=2013):
        '''
        The simulate function includes the simulation of the household 
        occupancies, plug loads, lighting loads and hot water tappings.
        '''

        self.year = year
        self.dow, self.nday = self.__chronology__(year)
        self.occ, self.occ_m = self.__occupancy__()
        self.test = self.__plugload__()

    def __chronology__(self, year):
        '''
        A basic internal calendar is made, storing the days and months of the
        depicted simulating year.
        - Monday == 0 ... Sunday == 6
        '''
        # first we determine the first week of the depicted year
        fdoy = datetime.datetime(year,1,1).weekday()
        fweek = range(7)[fdoy:]
        # whereafter we fill the complete year
        nday = 366 if calendar.isleap(year) else 355
        day_of_week = (fweek+53*range(7))[:nday]
        # and return the day_of_week for the entire year
        return day_of_week, nday

    def __occupancy__(self, min_form = True, min_time = False):
        '''
        Simulation of a number of days based on cluster 'BxDict'.
        - Including weekend days,
        - starting from a regular monday at 4:00 AM.
        '''
        def check(occday, RED, min_form = True, min_time = False):
            '''
            We set a check which becomes True if the simulated day behaves 
            according to the cluster, as a safety measure for impossible
            solutions.
            '''
            # First we check if the simulated occ-chain has the same shape
            location = np.zeros(1, dtype=int)
            reduction = occday[0]*np.ones(1, dtype=int)
            for i in range(len(occday)-1):
                if occday[i+1] != occday[i]:
                    location = np.append(location, i+1)
                    reduction = np.append(reduction,occday[i+1])
            shape = np.array_equal(reduction, RED)
            # And second we see if the chain has nu sub-30 min differences
            length = True
            if min_time:
                minlength = 99
                for i in location:
                    j = 0
                    while occday[i+j] == occday[i] and i+j < len(occday)-1:
                        j = j+1
                    if j < minlength:
                        minlength = j
                # and we neglect the very short presences of 20 min or less
                length = not minlength < 3
            # both have to be true to allow continuation
            return shape and length

        def dayrun(start, cluster):
            '''
            Simulation of a single day according to start state 'start'
            and the stochastics stored in cluster 'BxDict'and daytype 'Bx'.
            '''
            # set the default dayCheck at False
            daycheck = False
            endtime = datetime.datetime.utcnow() + datetime.timedelta(seconds = 10)
            # and then keep simulating a day until True
            SA = stats.MCSA(cluster)
            while daycheck == False:
                # set start state conditions
                tbin = 0
                occs = np.zeros(144, dtype=int)
                occs[0] = start
                t48 = np.array(sorted(list(range(1, 49)) * 3))
                dt = SA.duration(start, t48[0])
                # and loop sequentially transition and duration functions
                while tbin < 143:
                    tbin += 1
                    if dt == 0:
                        occs[tbin] = SA.transition(occs[tbin-1], t48[tbin])
                        dt = SA.duration(occs[tbin], t48[tbin]) - 1
                        # -1 is necessary, as the occupancy state already started
                    else:
                        occs[tbin] = occs[tbin - 1]
                        dt += -1
                # whereafer we control if this day is ok
                daycheck = check(occs, SA.RED)
                # and we include a break if the while takes to long 
                if datetime.datetime.utcnow() > endtime:
                    break
            # and return occs-array if daycheck is ok according to Bx
            return occs

        def merge(occ):
            '''
            Merge the occupancy profiles of all household members to a single
            profile denoting the number of present people.
            '''
            occs = int(3)*np.ones(len(occ[0])) # starting with least active state
            for member in occ:
                for to in range(len(member)):
                    if member[to] < occs[to]:
                        occs[to] = member[to] 
            return occs

        # first we read the stored cluster data for occupancy
        cdir = os.getcwd()
        os.chdir(cdir+'\\Occupancies')
        occ_week = []
        for member in self.clusters:
            # get the first duration of the start state
            start = 2
            # and run all three type of days
            wkdy = dayrun(start, member['wkdy'])
            sat = dayrun(wkdy[-1], member['sat'])
            son = dayrun(sat[-1], member['son'])
            # and concatenate 
            week = np.concatenate((np.tile(wkdy, 5), sat, son))
            occ_week.append(week)
        occ_merg = merge(occ_week)
        # and combine the occupancy states for the entire year
        bins = 4*144
        start, stop = bins*self.dow[0], start+365*self.nday
        occ_year = []
        for line in range(len(occ_week)):
            occ_year.append(np.tile(occ_week,54)[line][start:stop])
        occ_merged = []
        occ_merged.append(np.tile(occ_merg,54)[start:stop])
        # and return them to the class object
        os.chdir(cdir)
        return occ_year, occ_merged

    def __plugload__(self):
        '''
        Simulation of the electric load based on the occupancies, cluster 
        and the present appliances.
        - Including weekend days,
        - starting from a regular monday at 4:00 AM.
        '''

        def receptacles(self):
            '''
            Simulation of the receptacle loads.
            '''
            load = []
            return load
    
        def lightingload(self):
            '''
            Simulate use of lighting for residential buildings based on the 
            model of J. Widén et al (2009)
            '''
    
            # parameters ######################################################
            # Simulation of lighting load requires information on irradiance
            # levels which determine the need for lighting if occupant.
            # The loaded solar data represent the global horizontal radiation
            # at a time-step of 1-minute for Uccle, Belgium
            file = open('Climate//irradiance.txt','r')
            data_pickle = file.read()
            file.close()
            irr = cPickle.loads(data_pickle)
    
            # script ##########################################################
            # a yearly simulation is basic, also in a unittest
            nday = self.nday
            nbin = 144
            minutes = self.nday * 1440
            occ_m = self.occ_m[0]
            # the model is found on an ideal power level power_id depending on 
            # irradiance level and occupancy (but not on light switching 
            # behavior of occupants itself)
            time = np.arange(0, (minutes+1)*60, 60)
            to = -1 # time counter for occupancy
            tl = -1 # time counter for minutes in lighting load
            power_max = 200
            irr_max = 200
            pow_id = np.zeros(minutes+1)
            for doy, step in itertools.product(range(nday), range(nbin)):
                to += 1
                for run in range(0, 10):
                    tl += 1
                    if occ_m[to] == int(1) or (irr[tl] >= irr_max):
                        pow_id[tl] = 0
                    else:
                        pow_id[tl] = power_max*(1 - irr[tl]/irr_max)
            # determine all transitions of appliances depending on the appliance
            # basic properties, ie. stochastic versus cycling power profile
            to = -1
            tl = -1
            prob_adj = 0.1 # hourly probability to adjust
            pow_adj = 40 # power by which is adjusted
            power = np.zeros(minutes+1)
            react = np.zeros(minutes+1)
            for doy, step  in itertools.product(range(nday), range(nbin)):
                to += 1
                for run in range(0, 10):
                    tl += 1
                    if occ_m[to] == 0:
                        power[tl] = pow_id[tl]
                    elif random.random() <= prob_adj:
                        delta = power[tl-1] - pow_id[tl]
                        delta_min = np.abs(delta - pow_adj)
                        delta_plus = np.abs(delta + pow_adj)
                        if delta > 0 and delta_min < np.abs(delta) :
                            power[tl] = power[tl-1]-pow_adj
                        elif delta < 0 and delta_plus < np.abs(delta):
                            power[tl] = power[tl-1]+pow_adj
                        else:
                            power[tl] = power[tl-1]
                    else:
                        power[tl] = power[tl-1]
    
            radi, conv = power*0.55, power*0.45
    
            result = {'time':time, 'occ':None, 'P':power, 'Q':react, 'QRad':radi, 
                      'QCon':conv, 'Wknds':None, 'mDHW':None}
    
            # output ##########################################################
            # only the power load is returned
            return result

        result = lightingload(self)
        print result['P']

        load = []
        return load

    def __dhwload__(self):
        '''
        Simulation of the domestic hot water tappings.
        - Including weekend days,
        - starting from a regular monday at 4:00 AM.
        '''

        load = []
        return load

    def __shsetting__(self):
        '''
        Simulation of the space heating setting points.
        - Including weekend days,
        - starting from a regular monday at 4:00 AM.
        '''

        setting = []
        return setting

class Equipment(object):
    '''
    Data records for appliance simulation based on generated activity and
    occupancy profiles
    '''
    # All object parameters are given in kwargs
    def __init__(self, **kwargs):
        # copy kwargs to object parameters 
        for (key, value) in kwargs.items():
            setattr(self, key, value)
