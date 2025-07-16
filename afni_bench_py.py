#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#plot geometric mean for 
# bigger speed test
#  https://sscc.nimh.nih.gov/afni/doc/misc/afni_speed/index_html

import pandas as pd
import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt
df = pd.DataFrame({'CPU': ['12900k','12900k','12900k','12900k','12900k', 'M2','M2','M2','M2','M2','7950x3d','7950x3d','7950x3d','7950x3d','7950x3d','7950f','7950f','7950f','7950f','7950f','7950c','7950c','7950c','7950c','7950c', 'M4','M4','M4','M4','M4'],
					'Threads': [1,2,4,8,16, 1,2,4,8,16, 1,2,4,8,16, 1,2,4,8,16, 1,2,4,8,16, 1,2,4,8,16],
					'Time': [76,59,46,40,36, 68,52,43,38,38, 62,44,35,30,28, 55,39,31,27,27, 61,43,34,29,29, 46,37,32,29,28]})
sns.set()
ax = sns.lineplot(x='Threads', y='Time', hue='CPU', data=df, marker='o')
#plt.show()
plt.savefig('afni_bench.png', dpi=300)
