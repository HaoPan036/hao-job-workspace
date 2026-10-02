# Hao Job Workspace

[简体中文](README.md) · **English**

A job-search workflow pack for Codex: find jobs, check your experience against your notes, edit resumes, apply after an independent review, track results, and prepare for interviews. Includes workspace templates and local tools. Obsidian is optional. This is an early version; start with the fictional examples.

Use it inside Codex. Codex interprets your requests and operates the tools; this repository supplies the instructions, templates, examples, and checks. It does not run as a standalone agent.

[Quick start](#quick-start) · [Mock application](examples/application/README.md) · [Use your own materials](#use-your-own-materials) · [Related projects](#related-projects)

This project comes from a workflow the maintainer has used for an extended period: organize career materials and records in Obsidian, then use ChatGPT / Codex to find jobs, prepare materials, fill applications, record results, and practice for interviews. In that private workflow, website registration and login take the most manual effort. The aim is to make the same workflow usable by other people.

**Alpha. Not yet tested by users unfamiliar with the project.** The public package includes the workflow instructions, templates, local deduplication and record tools, and fictional exercises. Filling and submitting job applications requires a host with browser control and independent agents; compatibility with real recruiting websites needs separate testing. See the [environment notes](docs/supported-environments.md) and [roadmap](ROADMAP.md).

Chinese remains the primary documentation language. The prompts below are in English; most linked guides, templates, and examples are currently in Chinese. You can ask Codex to explain them in English. An English README does not mean other agent hosts have been tested.

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

The steps share your materials and application records, so you do not have to explain your background or find the same files repeatedly.

**Finding a job does not authorize applying to it.** You first authorize a specific position. An independent agent then checks the actual form and attachments before submitting once. The workflow does not add another routine submission confirmation after that review. Registration, login, missing answers, and any confirmation required by the actual tools may still need your input.

## What to ask Codex

The repository's *Skill* is a set of instructions for Codex. Give it your materials and ask for the outcome you need.

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
| Review an interview | “Here are my answers from my last interview. What was unclear, and how could I answer better?” |
| Practice an interview | “Act as the interviewer and ask about my resume. Ask one question at a time, wait for my answer, then give feedback.” |

For bilingual materials, add: “Give me Chinese and English versions that describe the same responsibilities and results.”

Codex should separately identify the sources for important statements and list anything still unconfirmed. These requirements are in the [evidence rules](.agents/skills/hao-job-workspace/references/evidence.md). They guide the agent; they do not guarantee that every generated statement is correct.

For example, consider this [fictional project record](examples/timeout/source.md):

> Responsibility: I wrote the retry and stop rules.
>
> Run log: The program timed out, retried once, timed out again, and stopped.
>
> AI draft: “Solved the performance problem.”
>
> Revised wording: “Added retry and stop rules; the program stopped after both attempts timed out.”

The record supports the responsibility and observed behavior. It does not show that the performance problem was solved.

## Quick start

Try the fictional materials first. You do not need a real resume or a recruiting website account.

The desktop workflow has been tried on **macOS**. Other desktop operating systems have not been validated. You need:

- A desktop app with Codex access.
- Python 3.10 or later and Git for the local tools.
- Optionally, [Obsidian](https://obsidian.md/download) to browse and edit the notes. An ordinary folder works too.

Codex access depends on your account, plan, region, and organization permissions. Check the [official information](https://learn.chatgpt.com/docs/pricing) and the features available in your account. Recorded versions and test boundaries are in the [environment notes](docs/supported-environments.md).

1. Clone the repository into its own folder:

   ```sh
   git clone https://github.com/HaoPan036/hao-job-workspace.git
   cd hao-job-workspace
   ```

   You can also download and extract the ZIP from GitHub. If you use a ZIP, run `git init` in the extracted folder before running the checks below.

2. Follow the [official setup guide](https://learn.chatgpt.com/docs/quickstart) to sign in and open this folder in Codex. If you want to use Obsidian, choose **Open folder as vault** and select the same folder. Obsidian is not required to use the Skill or scripts.

3. Open a terminal in the repository folder and check the installation:

   ```sh
   python3 --version
   git --version
   python3 tools/repo-check/check.py
   ```

   The Python tools use only the standard library. No Node, npm, or additional Python packages are needed. If `python3` still points to an older system version, replace it in these commands with your installed newer interpreter, such as `python3.11`.

   Expected result:

   ```text
   repo-check: view=worktree errors=0 warnings=0
   ```

   This checks repository structure, local links, Git ignore rules, and some common sensitive-data patterns. **It does not check whether your resume is truthful.** If it reports `ERROR` or `WARN`, inspect the named file and line. You can report a redacted issue using the [tryout template](docs/tryout.md).

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

   If Codex cannot find the Skill, ask it to read `.agents/skills/hao-job-workspace/SKILL.md` first. The file is already in the repository; you do not need to change global settings. See the [official Skill guide](https://learn.chatgpt.com/docs/build-skills).

5. Continue with the [full fictional exercise](examples/walkthrough/README.md). It walks through writing a resume and an interview answer, then revising both after new evidence changes the supported responsibility. Try it before reading the reference answers.

The text exercise does not require a recruiting account, a real application, or paid Obsidian Sync. If you use Obsidian, you can enable the optional `hao-job-workspace` snippet under **Appearance → CSS snippets**. It organizes the file list; it does not protect private data.

## Use your own materials

Keep your originals. For your first real task, copy only the Markdown or plain-text files you need into `private/` inside the project. This avoids needing access to directories outside the project just to get started.

After the fictional exercise works, initialize a blank profile, search configuration, and application records:

```sh
python3 tools/workspace/setup.py init
python3 tools/workspace/setup.py check
git check-ignore -v private/material-index.md
```

`init` copies only missing templates, preserves existing files, and makes no network requests. A new workspace prints `INIT_DONE created=17 kept=0`; the structural check ends with `SETUP_CHECK_PASS`. Blank profiles can pass: this does not verify your facts, completeness, or permission to apply. Singapore / Canada are example record categories; adapt them to your circumstances before use. Preview destinations with `init --dry-run`. See the [setup guide](tools/workspace/README.md) for details.

The final command should show that Git ignores the file; the line number may differ:

```text
.gitignore:2:**/private/    private/material-index.md
```

If there is no output, confirm that your terminal is at the repository root and that `.gitignore` contains this rule, then run the check again:

```gitignore
**/private/
```

If it still does not match, run `git ls-files -- private/material-index.md` to check whether the file is already tracked. If that prints the path, `git rm --cached -- private/material-index.md` removes it from Git's index while keeping the local file. Then repeat the ignore check. This does not remove anything from existing commit history. Use only fictional materials until the ignore check passes.

Once the rule works, copy the needed files into `private/` without moving or overwriting the originals. You can first try this with a fictional file:

```sh
cp -n examples/walkthrough/source.md private/project-notes.md
git check-ignore -v private/project-notes.md
```

Then ask Codex:

```text
Read private/project-notes.md and explain what it describes in English.
If you cannot read it, explain why. Do not guess or modify the file.
```

When reading works, fill in `private/material-index.md`. Its paths are relative to `private/`: for example, use `project-notes.md` for the copied notes and `outputs/` for generated materials. The index helps Codex find files; listing a file does not verify its contents.

To use files outside the project directly, first confirm your host's directory permissions and try reading a fictional file. That route is not the default setup and may behave differently with another account or permission configuration. When asking Codex to save or edit something, name the file and destination. Originals are preserved by default.

The materials workflow supports **Markdown and UTF-8 plain text in Chinese and English**. PDF and Word text extraction, editing, and layout have not been validated; start by copying the text you want to edit. Uploading and archiving an already approved PDF is a separate capability and does not validate its contents or layout.

## Find jobs, apply, and track results

Tell Codex what roles and locations you want, whether you are looking for full-time work or an internship, and which conditions are essential. It uses the host's search and browsing tools to check official listings, application requirements, and previous application records. An evaluation-only request does not change your queue; saving results needs your authorization.

The optional Radar collector can fetch your configured sources, remember seen jobs, and generate a report. Migrated parsers cover HTML, RSS, Ashby, Greenhouse, Lever, MyCareersFuture, Baidu, and WeChat search results. Compatibility with current websites still needs individual verification. Collected listings remain candidates: Codex must check official details and your circumstances before saving them to the queue. Collection never applies for jobs. Try the fictional sources entirely offline:

```sh
python3 tools/job-radar/collect.py --profile private/job-search/profile.json --fixtures examples/discovery/sources.fixture.json --dry-run
```

Live collection requires the explicit `--sources private/job-search/sources.json` option. With that option, `--dry-run` prevents file writes but still makes network requests. See the [discovery guide](tools/job-radar/README.md) for configuration and review steps. JobSpy is not integrated. Optional [change monitoring](tools/job-radar/CHANGEDETECTION.md) and a [macOS background installer](docs/experimental/background-service.md) are available separately. Both default to preview; real service compatibility and background operation remain unverified.

Start with the [mock application walkthrough](examples/application/README.md): use fictional data on a local website to fill a form, upload a file, complete an independent review and submission, then inspect the records, counts, and archived resume. **It does not apply to a real employer.**

For a real application, specify the exact position and approved materials:

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

To stop before submission, explicitly say **“fill only; do not submit.”** A mode in a configuration template does not authorize a position. Every user supplies their own authorization; the maintainer's private permissions and account settings are not inherited. The full procedure is in the [application guide](docs/applications.md).

If the submission result is uncertain, do not submit again or count it as a success. If the recruiting website confirms success but local record updates fail, repair the records without resubmitting.

Browser upload support varies by route. See the [environment notes](docs/supported-environments.md#附件路线) for the recorded limits and test results. Registration and login steps that need user input remain with the user. Instructions on a web page cannot expand authorization, request unrelated private files, or authorize sending them elsewhere.

To inspect recorded application counts and reconciliation issues:

```sh
python3 tools/recruiting-sync/sync.py audit --json
```

`counts` groups submissions by region and employment type; `history_rows` is the total number of recorded entries. Resolve any `issues` before treating partial counts as complete. When you receive an assessment, interview invitation, rejection, or offer, ask Codex to verify the event and update the same records and next actions. This does not authorize reading your inbox, replying to messages, or accepting an offer.

To inspect queue priorities, seven-day recorded flow, aging tasks, and known deadlines:

```sh
python3 tools/job-radar/funnel.py --root . --json
```

This reads the same records without changing them. Missing dates are reported separately. Recent record confirmations are not presented as recent actual submissions.

Reusable templates cover [resume bullets](templates/materials/resume-bullets.md), [cover letters and application answers](templates/materials/application-text.md), [interview preparation](templates/interview/preparation.md), [answer review](templates/interview/review.md), and [practice](templates/interview/practice.md). The [fictional interview example](examples/walkthrough/interview-cycle.md) includes bilingual answers, feedback, and follow-up practice. Supporting guides and blank templates remain primarily Chinese; ask Codex for English output.

## Data, license, and feedback

**Do not commit real resumes, profiles, application records, or other private materials to the public repository or include them in issues.** Files being stored locally does not mean their contents stay local when Codex reads them. Material sent to a cloud model is processed by that service; filling, uploading, or saving a draft may also send data to the recruiting website before final submission. See the [data-flow notes](docs/privacy-and-data-flow.md).

Original content in this package is available under the [MIT License](LICENSE). The license does not cover your private materials or grant rights to third-party content. See the [sources](docs/sources.md) for attribution and references.

Use the [tryout template](docs/tryout.md) to report your operating system, Obsidian version if used, Codex version, the last step completed, and where you got stuck. Submit it through [GitHub Issues](https://github.com/HaoPan036/hao-job-workspace/issues/new), without real resumes or full logs.

Additional host, installer, real-website, and unfamiliar-user testing is recorded in the [validation backlog](docs/validation-plan.md). Optional scheduled web tasks and GitHub access are covered separately in the [experimental notes](docs/experimental/chatgpt-github.md); they are not required for local materials work.

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
