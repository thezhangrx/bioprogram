# Environment Factorial DAG Report

- 理论 nodes: 16; 理论 edges: 32
- 观测有效 nodes: 994
- 观测有效 edges: 2633
- METRIC_INCONSISTENCY edges: 0
- 有 CI 的 edges: 2633
- 异常阈值 |metric| > 10

## Groups

| split | cell_line | model | nodes | edges | inconsistency | unavailable |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| all | hct116 | cnn(3|3) | 16/16 | 32/32 | 0 |  |
| all | hct116 | cnn(5|3) | 16/16 | 32/32 | 0 |  |
| all | hct116 | cnn(7|3) | 16/16 | 32/32 | 0 |  |
| all | hct116 | linear | 8/16 | 12/32 | 0 | sequence_dnase, sequence_ctcf_dnase, sequence_dnase_h3k4me3, sequence_dnase_rrbs, sequence_ctcf_dnase_h3k4me3, sequence_ctcf_dnase_rrbs, sequence_dnas |
| all | hct116 | mlp | 16/16 | 32/32 | 0 |  |
| all | hct116 | transformer | 16/16 | 32/32 | 0 |  |
| all | hct116 | xgboost | 16/16 | 32/32 | 0 |  |
| all | hek293t | cnn(3|3) | 16/16 | 32/32 | 0 |  |
| all | hek293t | cnn(5|3) | 16/16 | 32/32 | 0 |  |
| all | hek293t | cnn(7|3) | 16/16 | 32/32 | 0 |  |
| all | hek293t | linear | 16/16 | 32/32 | 0 |  |
| all | hek293t | mlp | 16/16 | 32/32 | 0 |  |
| all | hek293t | transformer | 16/16 | 32/32 | 0 |  |
| all | hek293t | xgboost | 16/16 | 32/32 | 0 |  |
| all | hela | cnn(3|3) | 16/16 | 32/32 | 0 |  |
| all | hela | cnn(5|3) | 16/16 | 32/32 | 0 |  |
| all | hela | cnn(7|3) | 16/16 | 32/32 | 0 |  |
| all | hela | linear | 16/16 | 32/32 | 0 |  |
| all | hela | mlp | 16/16 | 32/32 | 0 |  |
| all | hela | transformer | 16/16 | 32/32 | 0 |  |
| all | hela | xgboost | 16/16 | 32/32 | 0 |  |
| all | hl60 | cnn(3|3) | 16/16 | 32/32 | 0 |  |
| all | hl60 | cnn(5|3) | 16/16 | 32/32 | 0 |  |
| all | hl60 | cnn(7|3) | 16/16 | 32/32 | 0 |  |
| all | hl60 | linear | 16/16 | 32/32 | 0 |  |
| all | hl60 | mlp | 16/16 | 32/32 | 0 |  |
| all | hl60 | transformer | 16/16 | 32/32 | 0 |  |
| all | hl60 | xgboost | 16/16 | 32/32 | 0 |  |
| mixed | none | cnn(3|3) | 16/16 | 128/32 | 0 |  |
| mixed | none | cnn(5|3) | 16/16 | 128/32 | 0 |  |
| mixed | none | cnn(7|3) | 16/16 | 128/32 | 0 |  |
| mixed | none | linear | 16/16 | 111/32 | 0 |  |
| mixed | none | mlp | 16/16 | 128/32 | 0 |  |
| mixed | none | transformer | 16/16 | 128/32 | 0 |  |
| mixed | none | xgboost | 16/16 | 128/32 | 0 |  |
| single | hct116 | cnn(3|3) | 16/16 | 32/32 | 0 |  |
| single | hct116 | cnn(5|3) | 16/16 | 32/32 | 0 |  |
| single | hct116 | cnn(7|3) | 16/16 | 32/32 | 0 |  |
| single | hct116 | linear | 16/16 | 32/32 | 0 |  |
| single | hct116 | mlp | 16/16 | 32/32 | 0 |  |
| single | hct116 | transformer | 16/16 | 32/32 | 0 |  |
| single | hct116 | xgboost | 16/16 | 32/32 | 0 |  |
| single | hek293t | cnn(3|3) | 16/16 | 32/32 | 0 |  |
| single | hek293t | cnn(5|3) | 16/16 | 32/32 | 0 |  |
| single | hek293t | cnn(7|3) | 16/16 | 32/32 | 0 |  |
| single | hek293t | linear | 16/16 | 32/32 | 0 |  |
| single | hek293t | mlp | 16/16 | 32/32 | 0 |  |
| single | hek293t | transformer | 16/16 | 32/32 | 0 |  |
| single | hek293t | xgboost | 16/16 | 32/32 | 0 |  |
| single | hela | cnn(3|3) | 16/16 | 32/32 | 0 |  |
| single | hela | cnn(5|3) | 16/16 | 32/32 | 0 |  |
| single | hela | cnn(7|3) | 16/16 | 32/32 | 0 |  |
| single | hela | linear | 16/16 | 32/32 | 0 |  |
| single | hela | mlp | 16/16 | 32/32 | 0 |  |
| single | hela | transformer | 16/16 | 32/32 | 0 |  |
| single | hela | xgboost | 16/16 | 32/32 | 0 |  |
| single | hl60 | cnn(3|3) | 16/16 | 32/32 | 0 |  |
| single | hl60 | cnn(5|3) | 16/16 | 32/32 | 0 |  |
| single | hl60 | cnn(7|3) | 16/16 | 32/32 | 0 |  |
| single | hl60 | linear | 10/16 | 14/32 | 0 | sequence_h3k4me3, sequence_dnase_h3k4me3, sequence_ctcf_dnase_h3k4me3, sequence_ctcf_h3k4me3_rrbs, sequence_dnase_h3k4me3_rrbs, all |
| single | hl60 | mlp | 16/16 | 32/32 | 0 |  |
| single | hl60 | transformer | 16/16 | 32/32 | 0 |  |
| single | hl60 | xgboost | 16/16 | 32/32 | 0 |  |
