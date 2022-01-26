import numpy as np
            
class Helpers:
    """
    A class to help make the db variable global
    
    instantiate with 
    
      helpers = Helpers(db)

      comp = helpers.comp

    then use with:
    
      comp(-1,-2)

    """
    def __init__(self, db):
        self._db = db
        
    
    def round_check(self, array, decimal=0):
    
        if isinstance(array.flat[0], np.floating):
            array = np.around(array,decimal)
        
        return array
    
    def comp(self, id_1, id_2,diff=True):

        """
        compare the baseline readings from two runs, optionally show all values

        Intended to be run in the IPython or Jupyter environment since it prints a table

        Parameters
        ----------
        id_1 : db identifier
            The first identifier
        id_2 : db identifier
            The first identifier
        diff : boolean
            show only the values which are different (to 4 decimal places)

        """



        run_a = self._db[id_1]
        run_b = self._db[id_2]
        baseline_a = run_a.baseline.read()
        variables_a = list(baseline_a.data_vars)

        baseline_b = run_b.baseline.read()
        variables_b = list(baseline_b.data_vars)

        common_vars = list(set(variables_a).intersection(variables_b))
        common_vars.sort()

        border = '+' + '-' * 32 + '+' + '-' * 32 + '+' + '-' * 32 + '+'
        print(border)
        print('| {:>30} | {:<30} | {:<30} |'.format('Signals',run_a.metadata['start']['scan_id'],run_b.metadata['start']['scan_id']))
        print(border)

        for var in common_vars:

            a = baseline_a[var][0].values
            b = baseline_b[var][0].values

            a = self.round_check(a,4)
            b = self.round_check(b,4)

            if a != b and diff:
                print('| {:>30} | {:<30} | {:<30} |'.format(var, a,b))
            elif not diff:
                print('| {:>30} | {:<30} | {:<30} |'.format(var, a,b))


        border = '+' + '-' * 32 + '+' + '-' * 32 + '+' + '-' * 32 + '+'
        print(border)