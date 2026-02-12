# CLAUDE.md Update Guidelines

## Core Principle

"Only add information that will genuinely help future Claude sessions. The context window is precious - every line must earn its place."

## What TO Add

### 1. Commands/Workflows Discovered
Document discovered build and dev commands with their purposes to prevent future rediscovery.

### 2. Gotchas and Non-Obvious Patterns
Record project-specific quirks like test execution requirements or dependency ordering that aren't apparent from code review.

### 3. Package Relationships
Capture architectural dependencies and import sequences that affect how modules interact.

### 4. Testing Approaches That Worked
Note which testing libraries and patterns prove effective within this codebase.

### 5. Configuration Quirks
Record environment-specific settings and runtime behaviors unique to the project.

## What NOT to Add

### 1. Obvious Code Info
Skip facts already communicated through class names or function signatures.

### 2. Generic Best Practices
Exclude universal development advice applicable to any project.

### 3. One-Off Fixes
Omit bug fixes unlikely to recur or historical context about past issues.

### 4. Verbose Explanations
Favor concise, focused information over detailed technical background.

## Diff Format for Updates

Present changes in three parts: file identification, concrete change using diff syntax, and rationale explaining the value to future sessions.

## Validation Checklist

Before finalizing updates, confirm:
- Each addition serves the specific project
- No generic advice appears
- Commands are tested
- File paths are correct
- Future sessions would benefit
- Information is expressed concisely
