# CANN Skills Specification

This repository follows the [Agent Skills specification](https://agentskills.io/specification).

Each skill is a directory containing a `SKILL.md` file with YAML frontmatter (`name`, `description`, `license`) and Markdown instructions, plus optional `scripts/`, `references/`, and `assets/` directories.

## CANN-Specific Conventions

- Skills target **Ascend NPU** with **CANN 8.5.0**
- Platform: aarch64, 48 AIVector Cores, 256KB UB per core
- All paths assume CANN installed at `/usr/local/Ascend/cann-8.5.0/`
- Scripts use bash and python3
