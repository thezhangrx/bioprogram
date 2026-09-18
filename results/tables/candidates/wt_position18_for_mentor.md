# WT → C18A 演示用代表性序列

候选池：`DeepCRISPR` 的 `single` 划分 test 集（无泄漏，seed=42）；挑选规则预先登记，未使用任何 C18A 结果。

| ID | Cell line | WT sequence (23 nt) | Pos18 | C18A sequence (23 nt) | Experimental efficiency | GC% | Selection reason |
| -- | --------- | ------------------- | ----- | --------------------- | -----------------------: | --: | ---------------- |
| WT01 | hct116 | `GACAGGAAGGTGCTGTACACAGG` | C | `GACAGGAAGGTGCTGTAAACAGG` | 0.110 | 55.0 | low 区间代表（最接近中位数 0.1101） |
| WT02 | hek293t | `TTATGGTGTGACAGTGCCTCCGG` | C | `TTATGGTGTGACAGTGCATCCGG` | 0.144 | 50.0 | low 区间代表（最接近中位数 0.1444） |
| WT03 | hek293t | `CCTTCAGCCTCCTTGTGCTCTGG` | C | `CCTTCAGCCTCCTTGTGATCTGG` | 0.214 | 60.0 | medium 区间代表（最接近中位数 0.2145） |
| WT04 | hela | `TCAGAATCCCATTCTTCCACAGG` | C | `TCAGAATCCCATTCTTCAACAGG` | 0.267 | 45.0 | medium 区间代表（最接近中位数 0.2671） |
| WT05 | hct116 | `ACCAACTACCAGCTGGGCACAGG` | C | `ACCAACTACCAGCTGGGAACAGG` | 0.537 | 60.0 | high 区间代表（最接近中位数 0.5368） |
| WT06 | hela | `TAATGCATCTGCCATCACGGTGG` | C | `TAATGCATCTGCCATCAAGGTGG` | 0.503 | 50.0 | high 区间代表（最接近中位数 0.5032） |
| WT07 | hl60 | `AGCCGGCCCGTAAGATCCGCAGG` | C | `AGCCGGCCCGTAAGATCAGCAGG` | 0.344 | 70.0 | 序列组成特殊但仍正常：GC 70.0% (全池中位 55.0%) |
| WT08 | hl60 | `GGCCGAAAGAGCCGTGGCCTTGG` | C | `GGCCGAAAGAGCCGTGGACTTGG` | 0.187 | 70.0 | 序列组成特殊但仍正常：GC 70.0% (全池中位 55.0%) |
