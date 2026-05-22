# oam-tools Repository Agent Skills Planning

## oam-tools Repository Skills List

> **Note**: `[x]` in the list indicates the skill is ready, `[ ]` indicates the skill is still being planned and not yet implemented.

- [x] **gitcode-issue** — Read Issue details, read and reply to comments. Trigger command: `Read issue 168 and submit PR to fix`
- [x] **gitcode-pr** — Create PR, submit inline review comments, cherry-pick code to commercial branches. Trigger command: `Review pr 1437` or `Create PR to develop branch`
- [ ] **superpowers** — Requirement development (generate software design documents, coding, generate test cases). Trigger command: `Develop requirement, requirements...`
- [ ] **oam-tools-reviewer** — Review code following various coding standards, coding rules, and module software design constraints
- [ ] **gitcode-pipeline** — Trigger pipeline tasks, query pipeline status, get failed task logs
- [ ] **oam-tools-dt-runner** — Compile and execute UT/ST cases
- [ ] **oam-tools-tester** — Generate cases, execute cases on environments with NPU
- [ ] **api-doc-generator** — Generate documentation for external APIs
- [ ] **install-cann-toolkit** — Download latest CANN toolkit package and install

## Processes Agent Needs to Support

- Requirement development: Complete the entire process from software design to coding to verification. Use gitcode-pr to submit PR, personally review code, gitcode-pipeline to trigger pipeline, and periodically get results. If pipeline fails, get corresponding failed task logs, locally modify code, submit PR again, and monitor pipeline.
- Issue fix: Modify code. The subsequent PR submission process is the same as above.
- Solve issue: Use gitcode-issue to read issue and comments. If code or document modification is involved, the process is the same as above.
- Execute test cases or examples: Use oam-tools-tester to execute cases in real environment

## oam-tools Repository Skills Path

- Project team shared, hope to achieve default installation or update when starting agent
- Skills only used in oam-tools repository can be directly submitted to oam-tools repository `.claude/skills` directory
- Skills shared by multiple repositories, source code in public repository (currently https://gitcode.com/cann-agent/skills). When starting agent, automatically download or update skills to `.claude/skills` directory

> **Note**: `gitcode-issue`, `gitcode-pr` and other cross-repository shared skills are not maintained in oam-tools repository `.claude/skills` directory. Their source code is stored in public repository. When starting agent in oam-tools directory, automatically download and install to local `.claude/skills` directory.

## Agent Auxiliary Process
```mermaid
flowchart TB
    subgraph Entry Node
        A1[Requirement Development]
        A2[Issue Fix]
        A3[Issue Processing]
    end

    subgraph Judgment
        B1{Need<br/>code modification?}
        B2{Need<br/>design phase?}
    end

    subgraph Design Phase
        C1[Software Design<br/>Requirement Specification]
    end

    subgraph Coding Verification Phase
        D1[Write Code]
        D2[Execute ut/st]
        D3[oam-tools-reviewer<br/>agent review code]
        D4[oam-tools-tester<br/>local verification]
    end

    subgraph PR Process
        E1[gitcode-pr<br/>Create PR]
        E2[Personal Code Review]
        E3[gitcode-pipeline<br/>Trigger Pipeline]
        E4[gitcode-pipeline<br/>Periodically Get<br/>Pipeline Results]
    end

    subgraph Pipeline Result Processing
        F1{gitcode-pipeline<br/>Pipeline<br/>passed?}
        F2[gitcode-pipeline<br/>Get Failed<br/>Task Logs]
        F3[Agent Local Fix]
    end

   subgraph Push Code
        I1[gitcode-pr<br/>Submit Code]
    end

    subgraph Complete
        H1[Process End]
    end

    %% Entry to Judgment
    A1 --> B2
    A2 --> B1
    A3 --> B1

    %% Design Judgment
    B2 -->|Yes| C1
    B2 -->|No| D1
    C1 --> D1

    %% Coding Judgment
    B1 -->|Yes| D1
    B1 -->|No| H1

    %% Coding to PR
    D1 --> D2
    D2 --> D3
    D3 --> D4
    D4 --> E1

    %% PR Process
    E1 --> E2
    E2 --> E3
    E3 --> E4
    E4 --> F1

    %% Pipeline Result Processing
    F1 -->|Passed| H1
    F1 -->|Failed| F2
    F2 --> F3
    F3 --> I1
    I1 --> E3

    ```