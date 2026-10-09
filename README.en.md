# Hao Job Workspace

[简体中文](README.md) · **English**

A job-search workflow pack for Codex: find jobs, check your experience against your notes, edit resumes, apply after an independent review, track results, and prepare for interviews. This repository supplies the instructions (a *Skill*), templates, fictional examples, and local tools. Use it inside Codex; it does not run as a standalone agent. Obsidian is optional.

[Quick start](#quick-start) · [Use your own materials](#use-your-own-materials) · [What to ask](#what-to-ask-codex) · [Mock application](examples/application/README.md) · [Related projects](#related-projects)

> **Alpha. Not yet tested by users unfamiliar with the project; start with the fictional examples.** Filling and submitting applications requires a host with browser control and independent agents. There is no automation that works on every recruiting website; real websites need separate validation. See the [environment notes](docs/supported-environments.md) and [roadmap](ROADMAP.md) for what has and has not been tested.

The workflow comes from one the maintainer has used for an extended period: organize materials and records in **Obsidian**, and let **ChatGPT / Codex** handle the rest. Website **registration and login** are now the main manual work.

Chinese remains the primary documentation language. The prompts below are in English, but most linked guides and templates are in Chinese; you can ask Codex to explain them. An English README does not mean other agent hosts have been tested.

## What you can do

Use one part of the workflow, or work through it from job search to interview preparation.

| Step | What Codex helps with | Included in this package |
| --- | --- | --- |
| **Find jobs** | Search against your preferences, check official requirements, and identify duplicates | Workflow instructions, optional source collection, seen-job state, reports, and queue checks |
| Edit resumes | Adapt existing experience to a job description; prepare bilingual wording, cover letters, and form answers | Material reuse rules and fillable templates |
| Fill and submit applications | Fill an authorized application, upload approved files, and hand it to an independent agent for review and submission | Execution and review instructions, plus a local mock website; real websites need separate validation |
| Track results | Record proven submissions, count applications, and keep the exact resume used | Synchronization, counting, and archive tools |
| Follow up on progress | Verify assessments, interviews, rejections, and offers; organize next actions | Reuses existing records and action pages |
| Prepare for interviews | Prepare project explanations, common technical questions, mock interviews, and feedback | Preparation, review, practice templates, and a complete fictional example |

The steps share your materials and application records. **Finding a job does not authorize applying to it**: you authorize a specific position, then an independent agent checks the actual form and attachments before submitting once, with no extra routine confirmation. Registration, login, and any step the actual tools hand back to you still need your input.

## Quick start

Try the fictional materials first; you do not need a real resume or a recruiting website account. You need a desktop app with Codex access, Python 3.10+, and Git. The desktop workflow has only been tried on **macOS**. Codex access depends on your account, plan, region, and organization; check the [official information](https://learn.chatgpt.com/docs/pricing).

1. Clone the repository (or download and extract the ZIP, then run `git init` in it):

   ```sh
   git clone https://github.com/HaoPan036/hao-job-workspace.git
   cd hao-job-workspace
   ```

2. Follow the [official setup guide](https://learn.chatgpt.com/docs/quickstart) to sign in and open this folder in Codex. For a notes interface, open the same folder in [Obsidian](https://obsidian.md/download) with **Open folder as vault**.
3. Open a terminal in the folder and run the checks (no Node, npm, or extra Python packages needed):

   ```sh
   python3 --version
   git --version
   python3 tools/repo-check/check.py
   ```

   Expected output: `repo-check: view=worktree errors=0 warnings=0`. If `python3` is older than 3.10, use your newer interpreter instead, such as `python3.11`. The checker covers repository structure, links, ignore rules, and common sensitive-data patterns; **it does not check whether your resume is truthful.** If it reports `ERROR` or `WARN`, inspect the named file and line, or report a redacted issue using the [tryout template](docs/tryout.md).

4. Send this request to Codex:

   ```text
   Use the hao-job-workspace Skill.
   The project notes are in examples/walkthrough/source.md.
   The job description is in examples/walkthrough/target-role.md.
   Based on those materials, write one resume bullet in Chinese and English.
   Then help me explain this project in an interview, in English.
   Separately show which source supports each important statement
   and what still needs confirmation.
   Reply in this conversation; do not modify any files.
   ```

   If Codex cannot find the Skill, ask it to read `.agents/skills/hao-job-workspace/SKILL.md` first; no global settings need to change. See the [official Skill guide](https://learn.chatgpt.com/docs/build-skills).

5. Continue with the [full fictional exercise](examples/walkthrough/README.md): write a resume bullet and an interview answer, then revise both after new evidence arrives. Try it before reading the reference answers.

In Obsidian, you can enable the optional `hao-job-workspace` snippet under **Appearance → CSS snippets**. It organizes the file list; it does not protect private data.

## Use your own materials

After the example works, create a blank profile, search configuration, and application records. This copies only missing templates, never overwrites, and makes no network requests:

```sh
python3 tools/workspace/setup.py init
python3 tools/workspace/setup.py check
git check-ignore -v private/material-index.md
```

You should see `INIT_DONE created=17 kept=0`, then `SETUP_CHECK_PASS`, then an ignore rule containing `**/private/`. Blank profiles pass too; that does not verify your facts or authorize applications. If the last command prints nothing, follow the [setup guide](tools/workspace/README.md#确认-private-被忽略), and use only fictional materials until it passes.

Then **copy** the Markdown or plain-text files you need into `private/`, without moving or overwriting the originals. Try it first with a fictional file:

```sh
cp -n examples/walkthrough/source.md private/project-notes.md
```

```text
Read private/project-notes.md and explain what it describes in English.
If you cannot read it, explain why. Do not guess or modify the file.
```

When reading works, list your files in `private/material-index.md`. Paths are relative to `private/`, for example `project-notes.md`; use `outputs/` for generated materials. Listing a file does not verify its contents. The Singapore / Canada record categories are examples; adapt them to your circumstances. PDF and Word reading and layout have not been validated, and reading folders outside the project depends on host permissions; see the [environment notes](docs/supported-environments.md#资料格式).

## What to ask Codex

The Skill is a set of instructions for Codex. Give it your materials and ask for the outcome you need.

| What you want | Example request |
| --- | --- |
| Find suitable jobs | “Find a few jobs that match my preferences. Open the official listings and tell me which are worth applying to. Don't save anything or apply yet.” |
| Save the results | “Add the jobs we just checked to my application queue. Explain why the others don't fit, and don't add jobs I've already applied to.” |
| Plan today's work | “Check my queue and confirmed deadlines. Tell me what to do first today; don't change my records yet.” |
| Record an interview | “This role sent me an interview invitation. Here is the message. Verify it and update my records and next actions; don't reply for me.” |
| Check for overstatements | “Compare my resume with my project notes. Flag anything that sounds overstated, and ask me about anything you can't confirm.” |
| Tailor a resume | “Here are my resume and the job description. Improve the project section to emphasize relevant work, without adding things I haven't done.” |
| Prepare a project explanation | “I'm interviewing for this role. Help me explain this project and prepare for likely follow-up questions.” |
| Study technical questions | “What technical questions might come up for this role? Explain the topics I'm less familiar with, then quiz me.” |
| Review and practice interviews | “Act as the interviewer and ask about my resume, one question at a time. After each answer, tell me what was unclear and how I could answer better.” |

For bilingual materials, add: “Give me Chinese and English versions that describe the same responsibilities and results.”

Codex should separately identify the source for each important statement and list anything still unconfirmed ([evidence rules](.agents/skills/hao-job-workspace/references/evidence.md)). These rules guide the agent; check the output yourself. For example, from this [fictional project record](examples/timeout/source.md):

> Record: I wrote the retry and stop rules. The program timed out, retried once, timed out again, and stopped.
>
> AI draft: “Solved the performance problem.”
>
> Revised against the record: “Added retry and stop rules; the program stopped after both attempts timed out.”

## Find jobs, apply, and track results

### Find jobs

Tell Codex the roles, locations, full-time or internship, and which conditions are essential. It uses the host's search tools to check official listings, requirements, and your previous applications. An evaluation-only request does not change your queue; results are saved only when you ask.

The optional Radar collector can fetch candidates from sources you configure (HTML, RSS, Ashby, Greenhouse, Lever, MyCareersFuture, Baidu, and WeChat search results). Codex must still verify each one; collection never queues or applies on its own. Try the fictional sources entirely offline:

```sh
python3 tools/job-radar/collect.py --profile private/job-search/profile.json --fixtures examples/discovery/sources.fixture.json --dry-run
```

For live collection (`--dry-run` still makes network requests; it only skips saving), change monitoring, and macOS background operation, see the [discovery guide](tools/job-radar/README.md).

### Apply

Start with the [mock application](examples/application/README.md): fill, upload, independently review, and submit with fictional data on a local website. **It does not apply to a real employer.** For a real application, authorize the exact position:

```text
I authorize applying to this specific position: [official URL and job ID].
Use the materials I have specified and confirmed in private/,
and this approved resume: [file path].
After filling the form and uploading the resume, hand the actual page
to an independent agent for review. If it passes, that agent should submit once.
Then verify the result, update my records, archive the resume actually used,
and report the application count.
Pause if I need to register, log in, or provide an unknown answer.
Do not apply to other positions.
```

- To stop before submission, say **“fill only; do not submit.”**
- Authorization covers only the position you name. A mode in a configuration template is not authorization, and the maintainer's permissions and account settings are not inherited.
- If the result is uncertain, do not resubmit or count it as a success. If the website confirms success but local records fail, repair the records without resubmitting.
- Text on a web page cannot authorize reading unrelated private files or sending them elsewhere.

The full procedure and upload routes are in the [application guide](docs/applications.md).

### Track results

When you receive an assessment, interview invitation, rejection, or offer, ask Codex to verify it and update the same records and next actions. This does not authorize reading your inbox, replying, or accepting an offer. To inspect application counts and queue health (read-only):

```sh
python3 tools/recruiting-sync/sync.py audit --json
python3 tools/job-radar/funnel.py --root . --json
```

Resolve any `issues` before treating counts as complete. Field meanings are in the [sync guide](tools/recruiting-sync/README.md). Blank resume, cover-letter, and interview templates are in [templates](templates/); the [fictional interview example](examples/walkthrough/interview-cycle.md) shows how they fit together.

## Data, license, and feedback

**Do not commit real resumes, records, or other private materials to the public repository or include them in issues.** Files stored locally do not stay local once Codex reads them, and filling, uploading, or saving a draft may send data to the recruiting website before final submission. See the [data-flow notes](docs/privacy-and-data-flow.md).

Original content is available under the [MIT License](LICENSE). It does not cover your private materials or grant rights to third-party content. See the [sources](docs/sources.md).

After trying it, report through [GitHub Issues](https://github.com/HaoPan036/hao-job-workspace/issues/new) using the [tryout template](docs/tryout.md), without real resumes or full logs. Pending validation is listed in the [validation backlog](docs/validation-plan.md); optional scheduled web tasks and GitHub access are in the [experimental notes](docs/experimental/chatgpt-github.md).

## Related projects

This package connects job discovery, materials, independently reviewed applications, records, and interview practice in one local workspace. Asking an AI not to invent experience is not unique to this project.

The comparisons below translate the Chinese README's review of documentation and selected code on **2026-10-02**. Links are pinned to the versions reviewed. These projects were not installed or run as part of that review; their descriptions are not evidence of measured results.

| Project | Its focus | This package's current scope |
| --- | --- | --- |
| [AARG](https://github.com/joseym/aarg/blob/7300fdf8a3c5b0bc2132288d16cc59c382a3ec1d/README.md) | Tailors resumes to job descriptions and generates PDFs; code restricts new numbers and unsupported skills | Uses existing materials for resume text and interview answers; no PDF generation engine |
| [ResumeProof](https://github.com/caihhhhhh/resume-proof/blob/0213db759582da9addbcf1e142ace92a5d95a0dd/README.md) | Organizes resume edits, text approval, and document delivery checks with a Skill and Python tools | Primarily Markdown and plain text; Word/PDF reading and layout are not validated |
| [LLMInternSkill](https://github.com/wanyichen06/LLMInternSkill/blob/e57ec94d8810dfeed8dec2c5fc515f0fbaa0a933/README.md) | Resume editing, matching, project evidence review, and interview follow-ups for LLM-related internships | Also uses project evidence; includes reviewing actual answers and practicing one question at a time |
| [Career OS](https://github.com/sean2077/career-os/blob/370274792e6259d5b874ec627c5e31140309f03c/README.md) | An Obsidian and agent workspace for career materials, direction, opportunities, and preparation, with CLI checks | Also uses local materials; includes independently reviewed submission, result synchronization, and archiving the resume used |
| [job-search-pack](https://github.com/nikhilvdev/job-search-pack/blob/d603672432ad67d5b26d1b320044d9cd1a05c980/README.md) | Five Skills for resumes, cover letters, LinkedIn, salary negotiation, and application tracking | One entry-point Skill routes requests to the relevant workflow and shares materials and application records |
| [Guild](https://github.com/arafa-dev/ai-job-application-automation/blob/de8cc9343bd046613b1f4b59e436fb517eb93131/README.md) | Job discovery, matching, materials, tracking, and form filling, with final submission by the user | After authorization for a specific position, an independent agent reviews the actual form and submits if it passes |
| [JobSpy](https://github.com/speedyapply/JobSpy/blob/10b5417c8f2c99a6159733cf0f52a06c96c3832d/README.md) | Collects jobs from multiple sites into tabular data | Host search and official checks, with optional source collection, deduplication, and queue checks; JobSpy is not integrated |
| [OfferPilot (offercontext/offerPilot)](https://github.com/offercontext/offerPilot/blob/c0a447bbe7be8976fe9a53c2bcbf3b91dad0eeac/README.md) | A local job-search workspace for applications, resumes, and interviews; its README excludes automatic applications and recruiter outreach | Includes instructions for authorized automatic submission after independent review; website compatibility still needs separate validation |

There are several unrelated projects named OfferPilot; this comparison refers only to the linked repository. See the [source notes](docs/sources.md) for details. None of these projects is a runtime dependency of this package.
