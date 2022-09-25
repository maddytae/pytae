import pandas as pd
import some_module

import settings
st=settings.PrepareSettings()




def run_something():
    some_module.test_code()
    print(st.user)
    print(settings.other_utils())
    
    
    
if __name__== '__main__':
    run_something()