# Kernel Analysis Summary

**Source File:** `kernel_details.csv`

---

## Overview

| Step ID | Kernel Count | Kernel Types | Total Duration (us) |
|---------|--------------|--------------|---------------------|
| 10 | 548 | 55 | 57131.2 |
| 11 | 548 | 55 | 17882.4 |
| 12 | 548 | 55 | 15786.1 |
| 13 | 548 | 55 | 17916.2 |
| 14 | 548 | 55 | 15416.2 |
| 15 | 548 | 55 | 17114.5 |
| 16 | 548 | 55 | 17905.3 |
| 17 | 548 | 55 | 15607.6 |
| 18 | 548 | 55 | 15071.4 |
| 19 | 548 | 55 | 17306.8 |

**Selected step:** auto-selected non-warmup step 15: largest stable kernel signature group size=10, skipped earliest warmup/outlier candidate=10, duration_us=17114.5, later_median_us=17114.5

---

## Kernel Types Distribution

### Steps 10, 11, 12, 13, 14, 15, 16, 17, 18, 19

| Kernel Name | Count |
|-------------|-------|
| Cast | 77 |
| MatMul | 49 |
| QuantBatchMatmulV3 | 36 |
| DynamicQuant | 33 |
| ConcatV2 | 30 |
| AivKernel | 28 |
| Add | 19 |
| SplitV | 18 |
| RotaryMul | 18 |
| ScatterNdUpdate | 18 |
| Transpose | 15 |
| DequantSwigluQuant | 15 |
| GatherV2 | 12 |
| GroupedMatmul | 12 |
| RmsNorm | 10 |
| MlaPrologV3 | 9 |
| LayerNormV3 | 9 |
| LightningIndexerQuant | 9 |
| KvQuantSparseFlashAttention | 9 |
| InplaceAddRmsNorm | 9 |
| ConcatD | 9 |
| HcomAllGather | 8 |
| Mul | 8 |
| MoeGatingTopKHash | 6 |
| MoeDistributeDispatchV2 | 6 |
| MoeDistributeCombineV2 | 6 |
| ArgMaxV2 | 5 |
| ArgMaxWithValue | 4 |
| Sub | 4 |
| OnesLike | 4 |
| hcom_allReduce | 4 |
| UpdateModelParam_static_bin | 4 |
| SubGreaterEqualLessLogicalAnd | 4 |
| HcomReduceScatter | 4 |
| BatchMatMul_to_tranpose_batch_matmul | 4 |
| HcomAllToAll | 4 |
| AddRmsNormDynamicQuant | 3 |
| Equal | 3 |
| AddRmsNorm/AddRmsNormCast | 3 |
| Reshape_58/ConfusionTranspose/Transpose | 3 |
| Fill | 2 |
| ReverseV2 | 2 |
| BatchMatMul_1_to_tranpose_batch_matmul | 1 |
| BatchMatMul_2_to_tranpose_batch_matmul | 1 |
| BatchMatMul_3_to_tranpose_batch_matmul | 1 |
| AddRmsNorm_3/AddRmsNormCast | 1 |
| BatchMatMul_4_to_tranpose_batch_matmul | 1 |
| AddRmsNorm_5/AddRmsNormCast | 1 |
| BatchMatMul_5_to_tranpose_batch_matmul | 1 |
| AddRmsNorm_7/AddRmsNormCast | 1 |
| Reshape_284/ConfusionTranspose/Transpose | 1 |
| ZerosLike | 1 |
| ReduceAny | 1 |
| SelectV2 | 1 |
| TensorMove | 1 |
