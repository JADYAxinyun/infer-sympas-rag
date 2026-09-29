# References and Code

- [SymPas paper](https://jcst.ict.ac.cn/fileup/1000-9000/PDF/2021-2-14-9754.pdf)
- [SymPas reference implementation: llvm-slicing](https://github.com/zhangyz/llvm-slicing)
- [Infer](https://github.com/facebook/infer)
- [DRaCo](https://github.com/nju-websoft/DraCo)
- [EESI–LLM](https://github.com/ucd-plse/eesi-llm)
- [Interleaving Static Analysis and LLM Prompting](https://github.com/ucd-plse/eesi-llm)

## Reproduction Boundary

The original SymPas implementation targets LLVM IR and an older toolchain. This project adapts the core algorithm to Infer SIL and should not claim byte-for-byte equivalence with the original implementation.
