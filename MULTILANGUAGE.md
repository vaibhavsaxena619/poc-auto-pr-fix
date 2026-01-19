# Multi-Language Support Documentation

This document explains how the AI-powered CI/CD pipeline now supports fixing errors across **6 programming languages** while maintaining security best practices.

---

## 🎯 **Quick Start**

### Supported Languages

```
✓ Java       (.java)  - Full compilation check via javac
✓ JavaScript (.js)    - Linting via eslint
✓ CSS        (.css)   - Styling via stylelint
✓ Shell      (.sh)    - Syntax check via bash -n
✓ Smarty     (.tpl)   - Template validation
✓ XSLT       (.xsl)   - XML transformation validation
```

### How It Works

1. **Detection:** File extension determines language
2. **Compilation:** Language-specific checker runs
3. **Classification:** Confidence scorer evaluates error type
4. **Confidence Gating:** Low-risk errors auto-fixed, high-risk require review
5. **Language-Specific Prompts:** Azure OpenAI gets tailored instructions
6. **Verification:** Code re-checked to ensure fix worked

---

## 🏗️ **Architecture**

### `language_config.py` - Language Registry

Central configuration file defining all language rules:

```python
# Example: JavaScript configuration
JAVASCRIPT_CONFIG = LanguageConfig(
    extension=".js",
    language=Language.JAVASCRIPT,
    compiler="eslint",
    
    safe_error_patterns={
        'syntax_error': r'SyntaxError|unexpected token',
        'undefined_var': r'cannot find module|ReferenceError'
    },
    
    risky_error_patterns={
        'injection': r'eval\(|innerHTML|XSS',
        'security': r'prototype pollution|credential'
    },
    
    fix_prompt_template="..."  # Language-specific AI prompt
    security_concerns=[...]     # Documented risks
)
```

**Each language config includes:**
- ✅ File extensions & patterns
- ✅ Compiler/checker command
- ✅ Safe error patterns (high confidence)
- ✅ Risky error patterns (low confidence)
- ✅ AI prompt template
- ✅ Security concerns list

### `build_fix.py` - Language-Agnostic Engine

Refactored to work with any language:

```python
def get_compilation_error(source_file: str) -> str:
    """Detects language and runs appropriate checker"""
    language = detect_language(source_file)
    config = get_language_config_by_file(source_file)
    # Runs config.compiler with config.compiler_args
    
def classify_error_confidence(error_msg: str, source_file: str):
    """Uses language-specific patterns for classification"""
    language = detect_language(source_file)
    return classify_error_by_language(error_msg, language)
```

**Key improvements:**
- ✅ No hardcoded Java references
- ✅ Language detection automatic
- ✅ Pattern matching per language
- ✅ Prompt templating per language

---

## 🔒 **Security by Language**

### Java

**Auto-Fix Enabled For:**
- Missing imports (`cannot find symbol`)
- Syntax errors (`unexpected token`)
- Test failures (`AssertionError`)

**Manual Review Required For:**
- 🚨 SQL injection risks
- 🚨 XXE vulnerabilities
- 🚨 Weak cryptography
- 🚨 Deserialization attacks
- 🚨 Hardcoded credentials

### JavaScript

**Auto-Fix Enabled For:**
- Syntax errors
- Undefined variables
- Missing imports
- Type errors

**Manual Review Required For:**
- 🚨 Command injection (`child_process.exec`)
- 🚨 Code execution (`eval`, `Function()`)
- 🚨 XSS attacks (`innerHTML`)
- 🚨 Prototype pollution
- 🚨 Hardcoded secrets

### CSS

**Auto-Fix Enabled For:**
- Property syntax errors
- Selector format
- Invalid values

**Manual Review Required For:**
- ⚠️ Specificity conflicts
- ⚠️ Performance issues (universal selectors)
- ⚠️ Browser compatibility
- ⚠️ IE vulnerabilities (`expression()`, `behavior:`)

### Shell (⚠️ HIGHEST RISK)

**Auto-Fix Enabled For:**
- Syntax errors
- Undefined variables
- Quote balancing

**Manual Review Required For:**
- 🚨 Shell injection (`$var` → `"$var"`)
- 🚨 Command substitution (`eval`, `$()`, backticks)
- 🚨 Hardcoded credentials
- 🚨 Dangerous commands (`rm -rf`, `dd`)
- 🚨 Privilege escalation (`sudo`, `root`)
- 🚨 Unsafe credentials in curl/wget

### Smarty

**Auto-Fix Enabled For:**
- Syntax errors
- Undefined variables
- Tag format

**Manual Review Required For:**
- 🚨 XSS injection (missing `|escape`)
- 🚨 Code execution (`{php}`, `{eval}`)
- 🚨 Template injection
- 🚨 Hardcoded secrets
- 🚨 Unsanitized includes

### XSLT

**Auto-Fix Enabled For:**
- XML syntax errors
- XPath expression format
- Namespace issues

**Manual Review Required For:**
- 🚨 XXE injection (External Entities)
- 🚨 Billion laughs DoS attack
- 🚨 Unsafe `disable-output-escaping`
- 🚨 Infinite recursion
- 🚨 Unvalidated entity references

---

## 🎛️ **Configuration Examples**

### Example 1: Fix JavaScript File

```bash
$ python3 build_fix.py src/app.js
[2026-01-19T14:15:30] Build fix initiated for src/app.js (javascript)
✗ Error detected
  Category: safe:syntax_error (confidence: 95%)
  ✓ HIGH CONFIDENCE: Safe to auto-fix
  Sending error to Azure OpenAI for analysis...
  ✓ SUCCESS: Fix verified!
```

### Example 2: Reject Shell Script (Risky)

```bash
$ python3 build_fix.py deploy.sh
[2026-01-19T14:16:45] Build fix initiated for deploy.sh (shell)
✗ Error detected
  Category: risky:injection (confidence: 10%)
  ⚠ LOW CONFIDENCE: Manual review required
  Aborting auto-fix (requires confidence >= 80%)
```

### Example 3: Feature Flag Control

```groovy
// Jenkinsfile
environment {
    // Auto-fix enabled by default
    ENABLE_AUTO_FIX = "true"
    
    // Read-only mode for risky languages
    READ_ONLY_MODE = "false"  // Set to true for shell scripts
}
```

---

## 📊 **Confidence Scoring Logic**

### High Confidence (≥80%)
```python
if error matches SAFE_ERROR_PATTERNS[language]:
    confidence = 0.9
    action = "AUTO-FIX"
```

**Safe patterns include:**
- Missing imports/includes
- Syntax errors (typos, brackets)
- Formatting issues
- Test failures
- Linting warnings

### Low Confidence (<80%)
```python
if error matches RISKY_ERROR_PATTERNS[language]:
    confidence = 0.1
    action = "MANUAL REVIEW REQUIRED"
```

**Risky patterns include:**
- Runtime errors (NPE, IndexOOB)
- Security issues (injection, XSS)
- Complex logic errors
- Infinite loops

---

## 🚀 **Adding a New Language**

### Step 1: Create Configuration

```python
# In language_config.py

NEW_LANGUAGE_CONFIG = LanguageConfig(
    extension=".new",
    language=Language.NEW_LANGUAGE,
    compiler="compiler-cmd",
    compiler_args=["--check"],
    file_patterns=[r"\.new$"],
    
    safe_error_patterns={
        'syntax_error': r'pattern1|pattern2',
        'import_error': r'pattern3|pattern4'
    },
    
    risky_error_patterns={
        'security': r'dangerous|unsafe'
    },
    
    fix_prompt_template="""
Fix the error in {source}:
{error}
""",
    
    review_prompt_template="...",
    security_concerns=["list", "of", "risks"]
)

# Register in LANGUAGE_CONFIGS
LANGUAGE_CONFIGS[Language.NEW_LANGUAGE] = NEW_LANGUAGE_CONFIG
```

### Step 2: Test

```bash
$ python3 build_fix.py test.new
# Should detect language and use appropriate checker
```

### Step 3: Update Documentation

- Add to SECURITY.md
- Update README.md
- Document language-specific risks

---

## 🔄 **Pipeline Integration**

### Jenkinsfile Multi-Language Build

```groovy
stage('Compile & Auto-Fix') {
    steps {
        script {
            // Find all source files
            sh '''
                # Compile Java
                javac -d build/classes src/*.java
                
                # Lint JavaScript
                eslint src/*.js
                
                # Check CSS
                stylelint src/*.css
                
                # Check Shell
                bash -n scripts/*.sh
            '''
        }
    }
    post {
        failure {
            // Runs build_fix.py for failed file
            sh 'python3 build_fix.py $FAILED_FILE'
        }
    }
}
```

---

## 📈 **Token Usage by Language**

| Language | Typical Error Size | Tokens Used | Cost |
|----------|---|---|---|
| Java | 200 bytes | ~50 | $0.0015 |
| JavaScript | 150 bytes | ~40 | $0.0012 |
| CSS | 100 bytes | ~30 | $0.0009 |
| Shell | 250 bytes | ~60 | $0.0018 |
| Smarty | 180 bytes | ~45 | $0.0013 |
| XSLT | 220 bytes | ~55 | $0.0016 |

**Total per fix:** ~$0.006 (after prompt optimization)

---

## ✅ **Best Practices Checklist**

- [ ] Shell scripts have `READ_ONLY_MODE=true`
- [ ] XSLT/Smarty reviewed before auto-fix
- [ ] JavaScript auth code excluded from build pipeline
- [ ] CSS changes reviewed for specificity
- [ ] Java migrations require manual approval
- [ ] Feature flags documented for team
- [ ] Confidence thresholds reviewed per language
- [ ] Security concerns from SECURITY.md understood
- [ ] Language-specific error patterns verified
- [ ] Test coverage for new language support

---

## 🤔 **FAQ**

**Q: Can I disable auto-fix for a specific language?**
A: Yes, set `ENABLE_AUTO_FIX=false` or create language-specific feature flags.

**Q: What if a language isn't detected correctly?**
A: Add pattern to `EXTENSION_TO_LANGUAGE` in `language_config.py`.

**Q: Can I customize confidence thresholds per language?**
A: Yes, modify `SAFE_ERROR_PATTERNS` and `RISKY_ERROR_PATTERNS` in config.

**Q: Is Shell always marked as low confidence?**
A: Shell follows same 80% threshold, but has more risky patterns detected.

**Q: How do I test new language support?**
A: Run `python3 build_fix.py test.ext` with a test file.
