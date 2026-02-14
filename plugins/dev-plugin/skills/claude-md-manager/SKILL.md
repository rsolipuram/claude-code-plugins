---
name: claude-md-manager
description: Intelligently manages CLAUDE.md - creates if missing, validates on start, updates with learnings on stop. Context-aware and follows official Anthropic guidelines.
tools: Read, Glob, Grep, Bash, Write, Edit
---

# CLAUDE.md Manager (Unified)

Intelligent, context-aware CLAUDE.md management using Claude's AI.

## Overview

This skill handles all CLAUDE.md operations:
- **Create**: When file is missing
- **Validate**: Quick quality check (SessionStart)
- **Update**: Add session learnings (Stop)

**Key Principle**: Use Claude's intelligence, not templates.

---

## Workflow

### Phase 1: Context Detection

Determine current situation and required action:

```bash
# Check if CLAUDE.md exists
if [ -f CLAUDE.md ]; then
  echo "Status: CLAUDE.md exists"
else
  echo "Status: CLAUDE.md missing"
fi
```

**Decision Matrix**:

| File Status | Hook Context | Action |
|-------------|--------------|--------|
| Missing | SessionStart | **Create** from scratch |
| Missing | Stop | **Create** (mandatory) + **Update** (if learnings exist) |
| Exists | SessionStart | **Validate** (quick check) |
| Exists | Stop | **Update** (only if learnings exist) |

**Important Notes**:
- **Missing file = ALWAYS create it**, even if session is empty. Future sessions need a starting point.
- **Updates are conditional** - only add content if valuable learnings were captured.

### Phase 2: Execute Action

Based on Phase 1 decision, execute appropriate workflow.

**CRITICAL RULE**: If CLAUDE.md is missing, you MUST create it - even if the session is empty. The CREATE action is mandatory when the file doesn't exist. Only the UPDATE portion is conditional on having learnings.

---

## Action 1: CREATE (When Missing)

**MANDATORY**: This action is REQUIRED whenever CLAUDE.md does not exist, regardless of session content.

### Step 1: Codebase Discovery

Analyze project structure to understand type:

```bash
# Find project indicators
ls -la | grep -E "(package.json|Cargo.toml|go.mod|pyproject.toml|pom.xml|Gemfile|composer.json)"

# Scan directory structure
find . -maxdepth 2 -type d | head -20

# Look for README
find . -maxdepth 2 -name "README*" | head -5
```

**Identify**:
- Project type (Node.js, Python, Go, Rust, etc.)
- Main source directories
- Configuration files
- Existing documentation

### Step 2: Deep Analysis

Read key files to understand the project:

**Priority files** (if they exist):
1. `README.md` - High-level overview
2. `package.json` / `Cargo.toml` / `pyproject.toml` / `go.mod` - Metadata
3. Main entry point - Understanding execution
4. Key configuration files

**Extract**:
- Project name and description
- Available scripts/commands
- Dependencies and tech stack
- Directory structure purpose

### Step 3: Intelligent Generation

**Create CLAUDE.md using your understanding** - NOT templates!

**Essential sections** (only if relevant):

#### Commands (High Priority)
```markdown
## Commands

| Command | Description |
|---------|-------------|
| `npm run dev` | Start development server on port 3000 |
| `npm test` | Run test suite with coverage |
```

#### Architecture (High Priority)
```markdown
## Architecture

\```
my-app/
  src/          # Application source code
  components/   # React components
  api/          # API endpoints
\```
```

#### Key Files (Medium Priority)
```markdown
## Key Files

- `src/index.ts` - Application entry point
- `src/config.ts` - Configuration loader
```

#### Gotchas (If Discovered)
```markdown
## Gotchas

- Tests require Docker to be running
- Must run `npm run codegen` before tests
```

### Step 4: Quality Verification

Before writing, verify:
- ✅ All commands are real (from package.json, Makefile, etc.)
- ✅ All file paths exist
- ✅ Architecture reflects actual directories
- ✅ No generic advice - everything project-specific
- ✅ Concise (aim for under 10KB)
- ✅ Each line adds value

### Step 5: Create File

Write CLAUDE.md using Write tool.

**Add footer**:
```markdown
---

*Last updated: [current date]*
*Managed by claude-md-manager skill. Quality target: 80+/100*
```

**Output**:
```
✨ Created CLAUDE.md for {project-name}

Documented:
- {n} commands
- {n} key directories
- {n} important files

Quality score: {self-assessed}/100
```

---

## Action 2: VALIDATE (SessionStart, File Exists)

Quick quality check of existing CLAUDE.md.

### Step 1: Read Current File

```bash
cat CLAUDE.md
```

### Step 2: Quick Assessment

Check against quality criteria:

| Criterion | Quick Check |
|-----------|-------------|
| Commands present | Are build/test/deploy commands there? |
| Architecture | Is structure documented? |
| Actionability | Can commands be copy-pasted? |
| Currency | Do referenced files exist? |
| Size | Is it under 10KB? |

### Step 3: Score & Decide

**If score > 70**: Skip silently (file is good)

**If score < 70**: Suggest improvements:
```
💡 CLAUDE.md quality: {score}/100

Consider adding:
- [Missing commands]
- [Architecture gaps]
```

**Don't auto-fix during SessionStart** - just report. User can manually improve or it will update during work.

---

## Action 3: UPDATE (Stop, File Exists)

**CONDITIONAL**: Update CLAUDE.md with session learnings ONLY if valuable learnings exist.

If the session was empty (no tool calls, no transcript), skip the update gracefully. The file should remain as-is.

### Step 1: Session Analysis

Review what happened during session:

**Analyze**:
- What files were modified/created?
- What commands were executed?
- What patterns or approaches were used?
- What gotchas or issues were encountered?
- What architectural decisions were made?

**Read current CLAUDE.md**:
```bash
cat CLAUDE.md
```

### Step 2: Learning Extraction

**Extract ONLY valuable learnings** - NOT everything!

#### ✅ DO Add:

**1. Commands/Workflows Discovered**
```markdown
Example: Discovered `npm run codegen && npm test` workflow
```

**2. Gotchas and Non-Obvious Patterns**
```markdown
Example: "Tests fail if database migrations aren't run first"
```

**3. Package Relationships**
```markdown
Example: "auth package must be imported before database package"
```

**4. Testing Approaches That Worked**
```markdown
Example: "Use `--coverage` flag to generate reports in coverage/"
```

**5. Configuration Quirks**
```markdown
Example: "PORT defaults to 3000 but Docker uses 8080"
```

#### ❌ DO NOT Add:

**1. Obvious Code Info**
```markdown
❌ "The User class has a name property"
```

**2. Generic Best Practices**
```markdown
❌ "Write tests for your code"
```

**3. One-Off Fixes**
```markdown
❌ "Fixed typo in line 42"
```

**4. Verbose Explanations**
```markdown
❌ "The application architecture follows a three-tier pattern..."
✅ "Three-tier: UI → API → Database"
```

### Step 3: Deduplication Check

Before adding:
- Is this already in CLAUDE.md?
- Is it obvious from existing docs?
- Would future sessions genuinely benefit?

**Skip update if**:
- No significant learnings identified
- All insights already documented
- Session was trivial (reading only)

### Step 4: Targeted Updates

If valuable learnings exist, update using Edit tool.

**Section routing**:
- New commands → `## Commands`
- Gotchas → `## Gotchas`
- Architecture insights → `## Architecture`
- Testing patterns → `## Testing`
- Configuration → `## Environment`

**Update timestamp**:
```markdown
*Last updated: [current date]*
```

### Step 5: Quality Check

After updating:
- ✅ Update is concise (<50 lines added ideally)
- ✅ No duplicate information
- ✅ All commands copy-paste ready
- ✅ File paths correct
- ✅ Still under size limit (10KB)

**Output**:

If updated:
```
📝 Updated CLAUDE.md

Added:
- [Brief description of additions]
```

If skipped:
```
✓ No significant learnings to document this session
```

---

## Quality Criteria (6 Dimensions)

### Scoring Rubric (100 points total)

1. **Commands/Workflows** (20 pts)
   - All essential commands documented with context
   - Build, test, lint, deploy present
   - Development workflow clear

2. **Architecture Clarity** (20 pts)
   - Key directories explained
   - Module relationships documented
   - Entry points identified
   - Data flow described where relevant

3. **Non-Obvious Patterns** (15 pts)
   - Gotchas and quirks captured
   - Known issues documented
   - Workarounds explained
   - Edge cases noted

4. **Conciseness** (15 pts)
   - Dense, valuable content
   - No filler or obvious info
   - Each line adds value
   - No redundancy

5. **Currency** (15 pts)
   - Commands work as documented
   - File references accurate
   - Tech stack current

6. **Actionability** (15 pts)
   - Instructions executable
   - Commands copy-paste ready
   - Steps concrete
   - Paths real

**Target**: 80+/100 (B grade or better)

---

## Configuration

Honor settings from `.claude/dev-plugin.local.md`:

```yaml
claude_md_management:
  auto_init: true           # Create if missing
  auto_update: true         # Update with learnings
  update_threshold: 3       # Min tool calls before update
  max_file_size: 10240     # Size limit (bytes)
  backup_before_update: true
```

**Respect thresholds**:
- If `auto_init: false` → Skip creation
- If `auto_update: false` → Skip updates
- If session < threshold → Skip update
- If file > max_size → Warn, skip update

---

## Examples

### Example 1: Create (TypeScript Project)

**Analysis finds**:
- `package.json` with scripts
- `tsconfig.json` configuration
- `src/` directory structure

**Generated CLAUDE.md**:
```markdown
# my-typescript-app

TypeScript web application

## Commands

| Command | Description |
|---------|-------------|
| `npm run dev` | Start dev server on :3000 |
| `npm run build` | Production build |
| `npm test` | Run vitest suite |

## Architecture

\```
my-app/
  src/
    components/   # React components
    hooks/        # Custom hooks
    utils/        # Utilities
\```

## Gotchas

- Dev server requires `VITE_API_URL` environment variable
```

### Example 2: Update (Session Learning)

**Session activity**:
- Ran tests, discovered Docker requirement
- Found database migration command
- Encountered port conflict

**Update**:
```markdown
## Gotchas

- Tests require Docker running (`docker ps` must work)
- Run `npm run db:migrate` before first test
- Default port 3000 conflicts - set PORT=3001 if needed
```

### Example 3: Validate (Good File)

**Existing CLAUDE.md scores 85/100**

**Output**:
```
✓ CLAUDE.md quality: 85/100 (Good)
```
*Silent - no action needed*

### Example 4: Validate (Poor File)

**Existing CLAUDE.md scores 45/100**

**Output**:
```
💡 CLAUDE.md quality: 45/100 (Needs improvement)

Missing:
- Build/test commands
- Architecture description
- Gotchas/patterns

Tip: Work on the project and this will auto-update at session end.
```

---

## Success Criteria

### For Creation
✅ CLAUDE.md exists and well-structured
✅ All commands work
✅ Architecture matches directories
✅ No template boilerplate
✅ Score: 80+/100

### For Updates
✅ Only valuable info added
✅ Concise and actionable
✅ No duplicates
✅ Human-readable
✅ Future sessions benefit

### For Validation
✅ Accurate assessment
✅ Helpful suggestions
✅ Non-intrusive

---

## What to AVOID

**Never do**:
- ❌ Use templates blindly
- ❌ Add obvious code info
- ❌ Include generic advice
- ❌ Log every change
- ❌ Be verbose
- ❌ Guess commands (verify!)
- ❌ Exceed size limits

**Always do**:
- ✅ Use your intelligence
- ✅ Verify everything
- ✅ Be project-specific
- ✅ Stay concise
- ✅ Test commands
- ✅ Think about future sessions

---

## Core Principles

1. **Intelligence > Templates**: Understand, don't fill blanks
2. **Quality > Quantity**: Every line earns its place
3. **Specific > Generic**: This project, not all projects
4. **Concise > Verbose**: Dense, valuable content
5. **Current > Aspirational**: What is, not what could be
6. **Actionable > Theoretical**: Copy-paste ready

---

## Reference Materials

See `references/` directory:
- `quality-criteria.md` - Detailed scoring rubric
- `templates.md` - Inspiration (not copy-paste)
- `update-guidelines.md` - What to add vs skip

Based on official Anthropic claude-md-management plugin.

---

*"Use Claude's intelligence to create living project documentation that genuinely helps future sessions."*
