#!/usr/bin/env python3
"""
Language configuration and detection module.
Provides language-specific rules, patterns, and handlers for multi-language CI/CD support.

Supported Languages:
- Java
- JavaScript
- CSS
- Shell (Bash)
- Smarty (Template)
- XSLT (XML Transformation)
"""

import re
from enum import Enum
from dataclasses import dataclass
from typing import Dict, List, Optional


class Language(Enum):
    """Supported programming languages."""
    JAVA = "java"
    JAVASCRIPT = "javascript"
    CSS = "css"
    SHELL = "shell"
    SMARTY = "smarty"
    XSLT = "xslt"
    UNKNOWN = "unknown"


@dataclass
class LanguageConfig:
    """Configuration for a specific language."""
    extension: str
    language: Language
    compiler: Optional[str]  # Command to compile/check
    compiler_args: List[str]  # Arguments for compiler
    file_patterns: List[str]  # Regex patterns to detect files
    
    # Error patterns for confidence scoring
    safe_error_patterns: Dict[str, str]  # High confidence fixes
    risky_error_patterns: Dict[str, str]  # Low confidence (manual review)
    
    # AI prompt template
    fix_prompt_template: str
    review_prompt_template: str
    
    # Language-specific security concerns
    security_concerns: List[str]


# === LANGUAGE CONFIGURATIONS ===

JAVA_CONFIG = LanguageConfig(
    extension=".java",
    language=Language.JAVA,
    compiler="javac",
    compiler_args=["-d", "build/classes"],
    file_patterns=[r"\.java$"],
    
    safe_error_patterns={
        'missing_import': r'cannot find symbol.*import|package.*not found|unresolved import',
        'formatting': r'expected|unexpected token|invalid syntax',
        'test_failure': r'AssertionError|Test.*failed|FAILED',
        'lint': r'unused|warning|dead code'
    },
    
    risky_error_patterns={
        'business_logic': r'NullPointerException|IndexOutOfBoundsException|logic',
        'security': r'SQL injection|XSS|vulnerability|deprecated',
        'migration': r'database|schema|ALTER|migration'
    },
    
    fix_prompt_template="""
TASK: Fix Java compilation error

ERROR:
{error}

SOURCE CODE:
{source}

REQUIREMENTS:
- Provide ONLY the corrected Java code
- Fix the exact error without refactoring
- Maintain the same class structure
- Use standard Java imports

RESPONSE: Only corrected Java code, no explanations.""",
    
    review_prompt_template="""
TASK: Review Java code in pull request

CODE DIFF:
{diff}

ANALYSIS FOCUS:
- Java best practices and conventions
- Memory leaks and resource management
- Thread safety and concurrency issues
- Exception handling and error recovery
- Security vulnerabilities in Java context

RESPONSE FORMAT:
## Code Review
- Positive points
- Issues found (critical/major/minor)
- Suggestions
- Security concerns""",
    
    security_concerns=[
        "Null pointer dereferences without null checks",
        "SQL injection from unsafe query construction",
        "Deserialization attacks (ObjectInputStream)",
        "Weak cryptography (MD5, SHA1)",
        "Hardcoded credentials",
        "XXE injection in XML parsing"
    ]
)

JAVASCRIPT_CONFIG = LanguageConfig(
    extension=".js",
    language=Language.JAVASCRIPT,
    compiler="node",  # Can also use eslint for linting
    compiler_args=["--check"],  # Will use eslint or equivalent
    file_patterns=[r"\.js$"],
    
    safe_error_patterns={
        'syntax_error': r'SyntaxError|unexpected token|expected|invalid',
        'missing_import': r'cannot find module|ReferenceError.*not defined|require.*not found',
        'type_error': r'TypeError.*not a function|not iterable|no such method',
        'test_failure': r'AssertionError|Test.*failed|FAILED|FAIL'
    },
    
    risky_error_patterns={
        'async_logic': r'Promise rejection|async.*await|callback hell|race condition',
        'security': r'eval\(|innerHTML|innerHTML=|XSS|injection|prototype pollution',
        'node_specific': r'fs\.readFileSync|fs\.writeFileSync|child_process.*exec|require.*eval'
    },
    
    fix_prompt_template="""
TASK: Fix JavaScript error

ERROR:
{error}

SOURCE CODE:
{source}

REQUIREMENTS:
- Provide corrected JavaScript code only
- Fix syntax and import errors
- Maintain existing code structure
- Use modern ES6+ syntax
- Ensure async/await properly handled

RESPONSE: Only corrected code, no explanations.""",
    
    review_prompt_template="""
TASK: Review JavaScript code

CODE:
{diff}

FOCUS AREAS:
- ES6+ best practices
- Async/Promise handling
- Security (XSS, injection, prototype pollution)
- Memory leaks and proper cleanup
- Module imports and dependencies
- Error handling

RESPONSE FORMAT:
## Code Review
- Strengths
- Issues (critical/major/minor)
- Recommendations""",
    
    security_concerns=[
        "eval() or Function() constructor usage",
        "innerHTML assignments (XSS risk)",
        "Prototype pollution attacks",
        "Unsafe deserialization of JSON",
        "Command injection via child_process.exec()",
        "Hardcoded secrets in code",
        "Dependency vulnerabilities"
    ]
)

CSS_CONFIG = LanguageConfig(
    extension=".css",
    language=Language.CSS,
    compiler="stylelint",  # CSS linter
    compiler_args=["--fix"],
    file_patterns=[r"\.css$"],
    
    safe_error_patterns={
        'syntax_error': r'parse error|unexpected|invalid property',
        'selector_error': r'selector not found|undefined selector',
        'property_error': r'unknown property|invalid value',
        'formatting': r'inconsistent spacing|wrong indent'
    },
    
    risky_error_patterns={
        'specificity': r'specificity conflict|selector override|cascade issue',
        'performance': r'universal selector \*|attribute selector|complex selector',
        'security': r'content.*javascript|data:text|expression\(|filter:|behavior:'
    },
    
    fix_prompt_template="""
TASK: Fix CSS error

ERROR:
{error}

STYLESHEET:
{source}

REQUIREMENTS:
- Fix CSS syntax errors only
- Maintain selector specificity
- Preserve media queries
- Use valid CSS3 properties
- Keep formatting consistent

RESPONSE: Only corrected CSS, no explanations.""",
    
    review_prompt_template="""
TASK: Review CSS stylesheet

CODE:
{diff}

EVALUATION CRITERIA:
- CSS3 compatibility
- Browser compatibility
- Performance (selectors, rendering)
- Accessibility implications
- Maintainability and DRY principle
- Mobile responsiveness

RESPONSE FORMAT:
## CSS Review
- Positive aspects
- Issues found
- Performance suggestions""",
    
    security_concerns=[
        "CSS expression() (IE vulnerability)",
        "Behavior property (IE vulnerability)",
        "Data URLs with JavaScript",
        "font-face with untrusted sources",
        "Content property injection"
    ]
)

SHELL_CONFIG = LanguageConfig(
    extension=".sh",
    language=Language.SHELL,
    compiler="bash",
    compiler_args=["-n"],  # Syntax check without execution
    file_patterns=[r"\.sh$", r"^[^.]+$"],  # .sh or no extension
    
    safe_error_patterns={
        'syntax_error': r'syntax error|unexpected|expecting|bad substitution',
        'undefined_var': r'not found|unbound variable|undefined',
        'quote_error': r'unmatched|unclosed|quote'
    },
    
    risky_error_patterns={
        'injection': r'eval|exec|\$\(|`|command substitution|variable expansion',
        'permissions': r'chmod|chown|sudo|uid=0|root',
        'file_ops': r'rm -rf|dd if=|mkfs|/dev/|partition',
        'network': r'curl.*-u|wget.*--password|ssh.*password'
    },
    
    fix_prompt_template="""
TASK: Fix shell script error

ERROR:
{error}

SCRIPT:
{source}

REQUIREMENTS:
- Fix syntax errors and undefined variables
- Use proper quoting for safety
- Avoid command injection vulnerabilities
- Use proper error handling
- Quote all variables: "${{var}}" not $var

RESPONSE: Only corrected shell script, no explanations.""",
    
    review_prompt_template="""
TASK: Review shell script

SCRIPT:
{diff}

SECURITY & QUALITY FOCUS:
- Shell injection vulnerabilities
- Proper quoting and escaping
- Error handling (set -e, trap)
- Hardcoded credentials
- Unsafe command chains
- File permission handling
- External command usage

RESPONSE FORMAT:
## Shell Script Review
- Strengths
- Security issues (CRITICAL)
- Quality issues
- Recommendations""",
    
    security_concerns=[
        "Shell injection via unquoted variables",
        "Command substitution injection ($(...), backticks)",
        "Hardcoded credentials and API keys",
        "Unsafe file operations (rm -rf, dd)",
        "Running with elevated privileges (sudo, root)",
        "Unsafe curl/wget with credentials",
        "eval() and exec() usage",
        "Insecure temporary file handling (/tmp without mktemp)"
    ]
)

SMARTY_CONFIG = LanguageConfig(
    extension=".tpl",
    language=Language.SMARTY,
    compiler=None,  # Smarty templates are compiled by framework
    compiler_args=[],
    file_patterns=[r"\.tpl$", r"\.smarty$"],
    
    safe_error_patterns={
        'syntax_error': r'Smarty error|parse error|syntax error|unexpected',
        'undefined_var': r'undefined variable|not defined|missing variable',
        'tag_error': r'unknown tag|invalid tag|unmatched'
    },
    
    risky_error_patterns={
        'injection': r'\{php\}|\{eval\}|php code|unsafe|untrusted input',
        'xss': r'html|javascript|script|onclick|onerror',
        'template_logic': r'complex logic|business logic|database|API'
    },
    
    fix_prompt_template="""
TASK: Fix Smarty template error

ERROR:
{error}

TEMPLATE:
{source}

REQUIREMENTS:
- Fix Smarty syntax and undefined variables
- Prevent XSS vulnerabilities
- Use |escape filter for user data
- Keep logic minimal in templates
- Use proper Smarty modifiers

RESPONSE: Only corrected Smarty template, no explanations.""",
    
    review_prompt_template="""
TASK: Review Smarty template

TEMPLATE:
{diff}

ANALYSIS AREAS:
- Smarty syntax correctness
- XSS prevention (escaped output)
- Variable scope and definition
- Filter usage (escape, stripslashes)
- Template logic complexity
- Hardcoded values vs. configuration
- Performance (loops, includes)

RESPONSE FORMAT:
## Template Review
- Positive aspects
- Issues found
- Security recommendations""",
    
    security_concerns=[
        "XSS via unescaped user output",
        "{php} tags allowing arbitrary PHP",
        "{eval} tags allowing code execution",
        "Unsanitized data in includes",
        "SQL injection through template variables",
        "Template injection attacks",
        "Hardcoded sensitive data in templates"
    ]
)

XSLT_CONFIG = LanguageConfig(
    extension=".xsl",
    language=Language.XSLT,
    compiler="xmllint",  # XML linter
    compiler_args=["--noout"],  # Validate without output
    file_patterns=[r"\.xsl$", r"\.xslt$"],
    
    safe_error_patterns={
        'syntax_error': r'parse error|XML error|unexpected element|invalid',
        'xpath_error': r'XPath error|invalid expression|unknown function',
        'namespace': r'namespace|prefix not defined|undefined|not found'
    },
    
    risky_error_patterns={
        'injection': r'disable-output-escaping.*yes|text\(\)|concat|string-join',
        'xxe': r'DTD|ENTITY|SYSTEM|file://|xxe|billion laughs',
        'logic': r'recursive|infinite loop|performance issue'
    },
    
    fix_prompt_template="""
TASK: Fix XSLT transformation error

ERROR:
{error}

STYLESHEET:
{source}

REQUIREMENTS:
- Fix XML/XSLT syntax errors
- Correct XPath expressions
- Maintain namespace definitions
- Prevent XXE vulnerabilities
- Use proper escaping

RESPONSE: Only corrected XSLT, no explanations.""",
    
    review_prompt_template="""
TASK: Review XSLT stylesheet

STYLESHEET:
{diff}

REVIEW FOCUS:
- XSLT 1.0/2.0 correctness
- XPath expression validity
- Namespace handling
- Security (XXE, injection)
- Performance (recursion, loops)
- Output encoding
- Template logic clarity

RESPONSE FORMAT:
## XSLT Review
- Strengths
- Issues found
- Security concerns
- Optimization suggestions""",
    
    security_concerns=[
        "XXE injection (XML External Entity)",
        "Billion laughs DoS attack (quadratic blowup)",
        "disable-output-escaping="yes" enabling injection",
        "Unvalidated external entity references",
        "Recursive template calls (infinite loops)",
        "Sensitive data in output",
        "DTD vulnerabilities"
    ]
)

# Language registry
LANGUAGE_CONFIGS: Dict[Language, LanguageConfig] = {
    Language.JAVA: JAVA_CONFIG,
    Language.JAVASCRIPT: JAVASCRIPT_CONFIG,
    Language.CSS: CSS_CONFIG,
    Language.SHELL: SHELL_CONFIG,
    Language.SMARTY: SMARTY_CONFIG,
    Language.XSLT: XSLT_CONFIG,
}

EXTENSION_TO_LANGUAGE: Dict[str, Language] = {
    '.java': Language.JAVA,
    '.js': Language.JAVASCRIPT,
    '.css': Language.CSS,
    '.sh': Language.SHELL,
    '.tpl': Language.SMARTY,
    '.smarty': Language.SMARTY,
    '.xsl': Language.XSLT,
    '.xslt': Language.XSLT,
}


def detect_language(file_path: str) -> Language:
    """
    Detect programming language from file extension.
    
    Args:
        file_path: Path to source file
        
    Returns:
        Detected Language or UNKNOWN
    """
    # Get file extension
    if '.' in file_path:
        ext = '.' + file_path.split('.')[-1].lower()
        return EXTENSION_TO_LANGUAGE.get(ext, Language.UNKNOWN)
    
    # Check for extensionless shell scripts
    if file_path.endswith('.sh') or file_path.endswith('_sh'):
        return Language.SHELL
    
    return Language.UNKNOWN


def get_language_config(language: Language) -> Optional[LanguageConfig]:
    """Get configuration for a specific language."""
    return LANGUAGE_CONFIGS.get(language)


def get_language_config_by_file(file_path: str) -> Optional[LanguageConfig]:
    """Get configuration by file path."""
    language = detect_language(file_path)
    return get_language_config(language)


def classify_error_by_language(error_message: str, language: Language) -> tuple[str, float]:
    """
    Classify error as safe or risky based on language-specific patterns.
    
    Returns:
        (category, confidence_score: 0.0-1.0)
    """
    config = get_language_config(language)
    if not config:
        return ("unknown", 0.5)
    
    error_lower = error_message.lower()
    
    # Check risky patterns first
    for risk_category, pattern in config.risky_error_patterns.items():
        if re.search(pattern, error_lower, re.IGNORECASE):
            return (f"risky:{risk_category}", 0.1)
    
    # Check safe patterns
    for safe_category, pattern in config.safe_error_patterns.items():
        if re.search(pattern, error_lower, re.IGNORECASE):
            return (f"safe:{safe_category}", 0.9)
    
    # Unknown error: default to low confidence
    return ("unknown", 0.5)


def get_compiler_command(language: Language, source_file: str) -> Optional[List[str]]:
    """
    Get compilation/checking command for a language.
    
    Returns:
        List of command and arguments, or None if not compilable
    """
    config = get_language_config(language)
    if not config or not config.compiler:
        return None
    
    cmd = [config.compiler, source_file]
    cmd.extend(config.compiler_args)
    return cmd


def is_language_supported(file_path: str) -> bool:
    """Check if file language is supported."""
    language = detect_language(file_path)
    return language != Language.UNKNOWN and language in LANGUAGE_CONFIGS


# === UTILITY FUNCTIONS ===

def get_all_supported_languages() -> List[str]:
    """Get list of all supported file extensions."""
    return list(EXTENSION_TO_LANGUAGE.keys())


def get_security_concerns(language: Language) -> List[str]:
    """Get language-specific security concerns."""
    config = get_language_config(language)
    return config.security_concerns if config else []
