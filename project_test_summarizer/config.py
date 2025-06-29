"""Configuration module for Project Test Summarizer."""

# Application constants
APP_NAME = "project_test_summarizer"
USER_ID = "test_analyzer_user"
SESSION_ID = "test_analysis_session"
GEMINI_MODEL = "gemini-2.5-flash-preview-05-20"

# State keys for session state
STATE_TARGET_PROJECT = "target_project_directory"
STATE_TEST_REPORTS = "discovered_test_reports"
STATE_EXTRACTED_TESTS = "extracted_test_names"
STATE_TEST_ANALYSIS = "test_analysis_results"
STATE_HUMAN_REPORT = "human_friendly_report"
STATE_AI_REPORT = "ai_friendly_report"
STATE_PROJECT_SUMMARY = "project_test_summary"

# Test analysis constants
NO_ISSUES_FOUND = "no_issues_found"
REPORT_OUTPUT_FILE = "test_analysis_report.json"

# Rate limiting settings (reuse from common)
RATE_LIMIT_MAX_CALLS = 10
RATE_LIMIT_WINDOW = 60

# Logging settings
LOG_FILENAME_FORMAT = "test_summarizer_%Y%m%d_%H%M%S.log"
LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
LOG_BACKUP_COUNT = 5

# Test framework patterns for discovery
TEST_REPORT_PATTERNS = [
    "**/test-results/**/*.xml",  # JUnit XML
    "**/test-results/**/*.json",  # JSON reports
    "**/test-results/**/*.html",  # HTML reports
    "**/target/surefire-reports/*.xml",  # Maven Surefire
    "**/target/failsafe-reports/*.xml",  # Maven Failsafe
    "**/build/test-results/**/*.xml",  # Gradle
    "**/build/reports/tests/**/*.html",  # Gradle HTML
    "**/pytest-report.xml",  # pytest XML
    "**/pytest-report.html",  # pytest HTML
    "**/coverage.xml",  # Coverage reports
    "**/junit.xml",  # Generic JUnit
    "**/test_results.xml",  # Generic test results
    "**/test-report.json",  # Generic JSON
    "**/.pytest_cache/**/*",  # pytest cache
]

# Common test file patterns for code discovery
TEST_FILE_PATTERNS = [
    "**/test_*.py",  # Python pytest pattern
    "**/*_test.py",  # Python pytest pattern
    "**/test*.py",  # Python unittest pattern
    "**/*Test.java",  # Java JUnit pattern
    "**/*Tests.java",  # Java JUnit pattern
    "**/Test*.java",  # Java JUnit pattern
    "**/*.test.js",  # JavaScript Jest pattern
    "**/*.spec.js",  # JavaScript Jasmine/Mocha
    "**/*.test.ts",  # TypeScript Jest pattern
    "**/*.spec.ts",  # TypeScript Jasmine/Mocha
    "**/test/**/*.py",  # Python test directory
    "**/tests/**/*.py",  # Python tests directory
    "**/src/test/**/*.java",  # Java Maven structure
    "**/src/test/**/*.kt",  # Kotlin test structure
]
