"""
Fairness Oriented Multiobjective Optimization (Fomo)

BSD 3-Clause License

Copyright (c) 2023, William La Cava

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import numpy as np
import pandas as pd

import random
#from pymoo.algorithms.base.genetic import GeneticAlgorithm
from pymoo.operators.selection.tournament import compare, TournamentSelection
from pymoo.algorithms.moo.nsga2 import NSGA2
from pymoo.algorithms.moo.nsga2 import binary_tournament
from fomo.utils import categorize
from pymoo.core.survival import Survival
from pymoo.core.selection import Selection
from pymoo.operators.sampling.rnd import FloatRandomSampling
from pymoo.operators.sampling.lhs import LatinHypercubeSampling
from pymoo.operators.survival.rank_and_crowding import RankAndCrowding
from pymoo.util.display.multi import MultiObjectiveOutput
from pymoo.termination.default import DefaultMultiObjectiveTermination
from pymoo.util.misc import has_feasible
from pymoo.operators.crossover.sbx import SBX
from pymoo.operators.mutation.pm import PM
from pymoo.algorithms.base.genetic import GeneticAlgorithm
from pymoo.operators.selection.rnd import RandomSelection
from sklearn.metrics import balanced_accuracy_score, log_loss

def get_parent(pop):

    if not hasattr(get_parent, "_called"):
        print("Default flex")
        get_parent._called = True
    
    group_loss = pop.get("group_loss")
    overall_loss = pop.get("overall_loss")
    G = np.arange(group_loss.shape[1])
    S = np.arange(len(pop))
    loss = []
    #epsilon = 0.001

    while (len(G) > 0 and len(S) > 1):

        g = random.choice(G)
        loss = []
        
        if (random.random() < 0.5):
            #half the time look at accuracy
            loss = group_loss[:, g]
        else:
            #half the time look at fairness
            loss = np.abs(group_loss[:, g] - overall_loss)

        L = min(loss) 
        epsilon = np.median(np.abs(loss - np.median(loss)))
        survivors = np.where(loss <= L + epsilon)
        S = S[survivors]
        group_loss = group_loss[survivors] 
        overall_loss = overall_loss[survivors]
        G = G[np.where(G != g)]
            
    S = S[:, None].astype(int, copy=False)     
    return random.choice(S)
                
def get_parent_noCoinFlip(pop):

    if not hasattr(get_parent_noCoinFlip, "_called"):
        print("Flex with no coin flip")
        get_parent_noCoinFlip._called = True

    group_loss = pop.get("group_loss")
    group_loss = np.tile(group_loss, 2)
    overall_loss = pop.get("overall_loss")
    G = np.arange(group_loss.shape[1])
    S = np.arange(len(pop))
    loss = []

    while (len(G) > 0 and len(S) > 1):

        g = random.choice(G)
        loss = []
        
        if g < max(G)/2:
            #look at accuracy
            loss = group_loss[:, g]
        else:
            #look at fairness
            loss = np.abs(group_loss[:, g] - overall_loss)

        L = min(loss) 
        epsilon = np.median(np.abs(loss - np.median(loss)))
        survivors = np.where(loss <= L + epsilon)
        S = S[survivors]
        group_loss = group_loss[survivors] 
        overall_loss = overall_loss[survivors]
        G = G[np.where(G != g)]

            
    S = S[:, None].astype(int, copy=False)     
    return random.choice(S)


def get_parent_WeightedCoinFlip(pop, group_loss, overall_loss, gp_lens, epsilon=0):

    if not hasattr(get_parent_WeightedCoinFlip, "_called"):
        print("Flex with weighted coin flip")
        get_parent_WeightedCoinFlip._called = True

    G = np.arange(group_loss.shape[1])
    S = np.arange(len(pop))
    #epsilon =0.001
    weight = random.random()

    while (len(G) > 0 and len(S) > 1):

        g = random.choice(G)
        loss = []

        if (random.random() > weight):
            #look at accuracy of the selected group
            loss = group_loss[:, g]
            G = G[np.where(G != g)]
 
        else:
            #look at accuracy of a random group
            ## if looking at FNR
            # num_rows, num_cols = np.shape(samples_loss)
            # indices = np.random.choice(num_cols, size = int(gp_lens[0, g]), replace = False)
            # fnr_sum = np.sum(samples_fnr[:, indices], axis=1)
            # pos_count = np.sum(samples_fnr[:, indices].astype(bool), axis=1)
            # for i in range (len(pos_count)):
            #     if pos_count[i]:
            #         loss.append(fnr_sum[i]/pos_count[i])
            #     else:
            #         loss.append(0)
            y_true = pop.get('y_true')
            y_pred = pop.get('y_pred')
            indices = np.random.choice(len(y_true[0]), size = int(gp_lens[g]), replace = False)
            for i in range(len(S)):
                loss.append(log_loss(y_true[i, indices], y_pred[i, indices], labels=[0, 1]))
            # indices = np.random.choice(samples_loss.shape[1], size = int(gp_lens[0, g]), replace = False)
            # loss = -1*np.mean(samples_loss[:, indices], axis=1)
        
        loss = np.array(loss)
        L = min(loss) 
        epsilon = np.median(np.abs(loss - np.median(loss)))
        survivors = np.where(loss <= L + epsilon)
        S = S[survivors]
        group_loss = group_loss[survivors] 
        overall_loss = overall_loss[survivors]
        #samples_loss = samples_loss[survivors]
            
    S = S[:, None].astype(int, copy=False)     
    return random.choice(S)

def get_parent_random(pop):
    
    if not hasattr(get_parent_random, "_called"):
        print("Random parent selection")
        get_parent_random._called = True
    
    return random.choice(pop)

def get_parent_add_test_case(pop):

    if not hasattr(get_parent_add_test_case, "_called"):
        print("Default flex with added test case for accuracy")
        get_parent_add_test_case._called = True
    
    overall_loss = pop.get("overall_loss")
    group_loss = pop.get("group_loss")
    G = np.arange(group_loss.shape[1]+1)
    S = np.arange(len(pop))
    #epsilon = 0.001

    while (len(G) > 0 and len(S) > 1):

        g = random.choice(G)
        loss = []
        if g == max(G):
            #test case for looking at overall accuracy
            loss = overall_loss
        
        else:
            #do default flex 
            if (random.random() < 0.5):
                loss = group_loss[:, g] # accuarcy of the group
            else:
                loss = np.abs(group_loss[:, g] - overall_loss) # fairness

        L = min(loss) 
        epsilon = np.median(np.abs(loss - np.median(loss)))
        survivors = np.where(loss <= L + epsilon)
        S = S[survivors]
        group_loss = group_loss[survivors] 
        overall_loss = overall_loss[survivors]
        G = G[np.where(G != g)]
            
    S = S[:, None].astype(int, copy=False)     
    return random.choice(S)

class FLEX(Selection):
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
     
         
    def _do(self, _, pop, n_select, n_parents=1, **kwargs):

        #samples_loss = pop.get("samples_loss")
        epsilon_type = kwargs['algorithm'].epsilon_type
        group_loss = pop.get("group_loss")
        overall_loss = pop.get("F")[:, 0]
        gp_lens = pop.get('gp_lens')[0]
        parents = []
        if epsilon_type == 'semi-dynamic':
            y_true = pop.get('y_true')
            y_pred = pop.get('y_pred')
            indices = np.random.choice(len(y_true[0]), size = int(random.choice(gp_lens)), replace = False)
            loss = []
            for i in range(len(pop)):
                loss.append(log_loss(y_true[i, indices], y_pred[i, indices]))
            epsilon = np.median(np.abs(loss - np.median(loss)))
            for i in range(n_select * n_parents): 
                #get pop_size parents
                p = get_parent_WeightedCoinFlip(pop, group_loss=group_loss, overall_loss=overall_loss, gp_lens=gp_lens, epsilon=epsilon)
                parents.append(p)
        else:
            for i in range(n_select * n_parents): 
                #get pop_size parents
                p = get_parent_WeightedCoinFlip(pop, group_loss=group_loss, overall_loss=overall_loss, gp_lens=gp_lens)
                parents.append(p)


        # selected = {}
        # population = {'X': pop.get('X').tolist(), 'F': pop.get('F').tolist(), 'id':pop.get('id').tolist(), 'fng': pop.get('fng').tolist()}
        # selected_parents = {'X': pop[parents].flatten().get('X').tolist(), 'F': pop[parents].flatten().get('F').tolist(), 'id':pop[parents].flatten().get('id').tolist(), 'fng': pop[parents].flatten().get('fng').tolist()}
        # selected['pop']= population
        # selected['parents']= selected_parents
        # import json
        # with open(f"/home/shakiba/flex/results/Run_15/synthetic0_no_evolution/populations/fomo_lex_lr_fnr_101_generation_{kwargs['algorithm'].n_iter}.json", 'w') as f:
        #     json.dump(selected, f, indent=2)

        return np.reshape(parents, (n_select, n_parents))

class LexSurvival(Survival):
    def __init__(self) -> None:
        super().__init__(filter_infeasible=False)

    def _do(self, problem, pop, n_survive=None, **kwargs):
        return pop[-n_survive:]


class Lexicase_NSGA2(GeneticAlgorithm):

    def __init__(self,
                 pop_size=100,
                 epsilon_type = 'dynamic',
                 sampling=FloatRandomSampling(),
                 selection=FLEX(),
                 crossover=SBX(eta=15, prob=0.9),
                 mutation=PM(eta=20),
                 survival=RankAndCrowding(),
                 output=MultiObjectiveOutput(),
                 **kwargs):
        
        super().__init__(
            pop_size=pop_size,
            sampling=sampling,
            selection=selection,
            crossover=crossover,
            mutation=mutation,
            survival=survival,
            output=output,
            advance_after_initial_infill=True,
            **kwargs)
        
        self.termination = DefaultMultiObjectiveTermination()
        self.tournament_type = 'comp_by_dom_and_crowding'
        self.epsilon_type = epsilon_type

    def _set_optimum(self, **kwargs):
        if not has_feasible(self.pop):
            self.opt = self.pop[[np.argmin(self.pop.get("CV"))]]
        else:
            self.opt = self.pop[self.pop.get("rank") == 0]

class Lexicase(GeneticAlgorithm):

    def __init__(self,
                 pop_size=100,
                 epsilon_type = 'dynamic',
                 sampling=FloatRandomSampling(),
                 selection=FLEX(),
                 crossover=SBX(eta=15, prob=0.9),
                 mutation=PM(eta=20),
                 survival=LexSurvival(),
                 output=MultiObjectiveOutput(),
                 **kwargs):
        
        super().__init__(
            pop_size=pop_size,
            sampling=sampling,
            selection=selection,
            crossover=crossover,
            mutation=mutation,
            survival=survival,
            output=output,
            advance_after_initial_infill=True,
            **kwargs)
        
        self.termination = DefaultMultiObjectiveTermination()
        self.epsilon_type = epsilon_type