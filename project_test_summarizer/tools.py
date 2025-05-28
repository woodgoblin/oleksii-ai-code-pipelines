"""Specialized tools for Project Test Summarizer - Test analysis and discovery."""

import glob
import os
import json
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Any, Optional
from pathlib import Path

from google.adk.tools import ToolContext
from common.logging_setup import setup_logging
from project_test_summarizer.config import (
    TEST_REPORT_PATTERNS, TEST_FILE_PATTERNS, 
    STATE_TARGET_PROJECT, REPORT_OUTPUT_FILE
)

# Set up logging for this module
logger = setup_logging("project_test_summarizer", redirect_stdout=False)

# --- Test Report Discovery Tools ---

def discover_test_reports(target_directory: str, tool_context: ToolContext | None = None) -> Dict[str, Any]:
    """Discover test reports in the target project using pattern matching."""
    try:
        if not os.path.exists(target_directory):
            return {"error": f"Target directory does not exist: {target_directory}"}
        
        logger.info(f"Discovering test reports in: {target_directory}")
        discovered_reports = []
        
        for pattern in TEST_REPORT_PATTERNS:
            # Convert glob pattern to work from target directory
            full_pattern = os.path.join(target_directory, pattern.lstrip("**/"))
            matches = glob.glob(full_pattern, recursive=True)
            
            for match in matches:
                if os.path.isfile(match):
                    relative_path = os.path.relpath(match, target_directory)
                    file_size = os.path.getsize(match)
                    
                    discovered_reports.append({
                        "file_path": relative_path,
                        "absolute_path": match,
                        "file_size": file_size,
                        "pattern_matched": pattern,
                        "file_extension": os.path.splitext(match)[1]
                    })
        
        # Remove duplicates based on absolute path
        unique_reports = []
        seen_paths = set()
        for report in discovered_reports:
            if report["absolute_path"] not in seen_paths:
                unique_reports.append(report)
                seen_paths.add(report["absolute_path"])
        
        return {
            "discovered_reports": unique_reports,
            "total_reports_found": len(unique_reports),
            "search_directory": target_directory,
            "patterns_used": TEST_REPORT_PATTERNS
        }
        
    except Exception as e:
        error_msg = f"Error discovering test reports in {target_directory}: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

def analyze_test_report_content(report_file_path: str, tool_context: ToolContext | None = None) -> Dict[str, Any]:
    """Analyze content of a test report file to extract test names and metadata."""
    try:
        if not os.path.exists(report_file_path):
            return {"error": f"Report file does not exist: {report_file_path}"}
        
        logger.info(f"Analyzing test report: {report_file_path}")
        file_extension = os.path.splitext(report_file_path)[1].lower()
        
        with open(report_file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        extracted_tests = []
        report_metadata = {
            "file_path": report_file_path,
            "file_size": len(content),
            "format_detected": "unknown"
        }
        
        if file_extension == '.xml':
            # Try to parse as XML (JUnit format)
            try:
                root = ET.fromstring(content)
                report_metadata["format_detected"] = "xml"
                
                # Look for JUnit-style test cases
                test_cases = root.findall(".//testcase")
                for test_case in test_cases:
                    test_name = test_case.get("name", "")
                    class_name = test_case.get("classname", "")
                    time_taken = test_case.get("time", "")
                    
                    # Check for failure or error elements
                    status = "passed"
                    failure_msg = ""
                    if test_case.find("failure") is not None:
                        status = "failed"
                        failure_elem = test_case.find("failure")
                        failure_msg = failure_elem.get("message", "") if failure_elem is not None else ""
                    elif test_case.find("error") is not None:
                        status = "error"
                        error_elem = test_case.find("error")
                        failure_msg = error_elem.get("message", "") if error_elem is not None else ""
                    
                    extracted_tests.append({
                        "test_name": test_name,
                        "class_name": class_name,
                        "full_name": f"{class_name}.{test_name}" if class_name else test_name,
                        "status": status,
                        "execution_time": time_taken,
                        "failure_message": failure_msg
                    })
                
                # Get test suite information
                test_suites = root.findall(".//testsuite")
                report_metadata["test_suites"] = len(test_suites)
                report_metadata["total_tests"] = sum(int(suite.get("tests", "0")) for suite in test_suites)
                
            except ET.ParseError:
                # Fallback to text parsing for malformed XML
                report_metadata["format_detected"] = "malformed_xml"
                extracted_tests = _extract_tests_from_text(content)
                
        elif file_extension == '.json':
            # Try to parse as JSON
            try:
                json_data = json.loads(content)
                report_metadata["format_detected"] = "json"
                extracted_tests = _extract_tests_from_json(json_data)
            except json.JSONDecodeError:
                report_metadata["format_detected"] = "malformed_json"
                extracted_tests = _extract_tests_from_text(content)
                
        elif file_extension == '.html':
            report_metadata["format_detected"] = "html"
            extracted_tests = _extract_tests_from_html(content)
        else:
            # Generic text parsing
            extracted_tests = _extract_tests_from_text(content)
        
        return {
            "extracted_tests": extracted_tests,
            "report_metadata": report_metadata,
            "total_tests_extracted": len(extracted_tests)
        }
        
    except Exception as e:
        error_msg = f"Error analyzing report file {report_file_path}: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

def analyze_multiple_test_reports(report_files: List[str], tool_context: ToolContext | None = None) -> Dict[str, Any]:
    """Analyze multiple test report files in a single call to extract test names and metadata.
    
    This is more efficient than calling analyze_test_report_content for each file individually,
    especially when dealing with 100+ report files.
    
    Args:
        report_files: List of file paths to analyze
        tool_context: Tool context (optional)
        
    Returns:
        Dict containing aggregated results from all reports
    """
    try:
        logger.info(f"Analyzing {len(report_files)} test reports in batch")
        
        all_extracted_tests = []
        all_report_metadata = []
        processing_errors = []
        total_tests_extracted = 0
        
        # Process each report file
        for i, report_file_path in enumerate(report_files):
            try:
                if not os.path.exists(report_file_path):
                    processing_errors.append({
                        "file_path": report_file_path,
                        "error": f"File does not exist: {report_file_path}"
                    })
                    continue
                
                logger.debug(f"Processing report {i+1}/{len(report_files)}: {report_file_path}")
                
                # Use the existing single-file analysis logic
                result = analyze_test_report_content(report_file_path, tool_context)
                
                if "error" in result:
                    processing_errors.append({
                        "file_path": report_file_path,
                        "error": result["error"]
                    })
                    continue
                
                # Aggregate the results
                extracted_tests = result.get("extracted_tests", [])
                report_metadata = result.get("report_metadata", {})
                
                # Add source file info to each test
                for test in extracted_tests:
                    test["source_report"] = report_file_path
                
                all_extracted_tests.extend(extracted_tests)
                all_report_metadata.append(report_metadata)
                total_tests_extracted += len(extracted_tests)
                
            except Exception as e:
                error_msg = f"Error processing {report_file_path}: {str(e)}"
                logger.error(error_msg)
                processing_errors.append({
                    "file_path": report_file_path,
                    "error": error_msg
                })
        
        # Generate summary statistics
        format_counts = {}
        for metadata in all_report_metadata:
            format_type = metadata.get("format_detected", "unknown")
            format_counts[format_type] = format_counts.get(format_type, 0) + 1
        
        # Deduplicate tests (same test might appear in multiple reports)
        unique_tests = []
        seen_test_signatures = set()
        
        for test in all_extracted_tests:
            # Create a signature for deduplication
            signature = f"{test.get('full_name', test.get('test_name', ''))}"
            if signature not in seen_test_signatures:
                unique_tests.append(test)
                seen_test_signatures.add(signature)
        
        return {
            "extracted_tests": all_extracted_tests,  # All tests including duplicates
            "unique_tests": unique_tests,  # Deduplicated tests
            "report_metadata": all_report_metadata,
            "processing_summary": {
                "total_reports_processed": len(report_files),
                "successful_reports": len(all_report_metadata),
                "failed_reports": len(processing_errors),
                "total_tests_extracted": total_tests_extracted,
                "unique_tests_found": len(unique_tests),
                "format_distribution": format_counts
            },
            "processing_errors": processing_errors
        }
        
    except Exception as e:
        error_msg = f"Error in batch analysis of test reports: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

def discover_test_files(target_directory: str, tool_context: ToolContext | None = None) -> Dict[str, Any]:
    """Discover test files in the target project using pattern matching."""
    try:
        if not os.path.exists(target_directory):
            return {"error": f"Target directory does not exist: {target_directory}"}
        
        logger.info(f"Discovering test files in: {target_directory}")
        discovered_test_files = []
        
        for pattern in TEST_FILE_PATTERNS:
            # Convert glob pattern to work from target directory
            full_pattern = os.path.join(target_directory, pattern.lstrip("**/"))
            matches = glob.glob(full_pattern, recursive=True)
            
            for match in matches:
                if os.path.isfile(match):
                    relative_path = os.path.relpath(match, target_directory)
                    file_size = os.path.getsize(match)
                    
                    discovered_test_files.append({
                        "file_path": relative_path,
                        "absolute_path": match,
                        "file_size": file_size,
                        "pattern_matched": pattern,
                        "language": _detect_language_from_extension(match)
                    })
        
        # Remove duplicates and sort by path
        unique_files = []
        seen_paths = set()
        for test_file in discovered_test_files:
            if test_file["absolute_path"] not in seen_paths:
                unique_files.append(test_file)
                seen_paths.add(test_file["absolute_path"])
        
        unique_files.sort(key=lambda x: x["file_path"])
        
        return {
            "discovered_test_files": unique_files,
            "total_test_files_found": len(unique_files),
            "search_directory": target_directory,
            "languages_detected": list(set(f["language"] for f in unique_files))
        }
        
    except Exception as e:
        error_msg = f"Error discovering test files in {target_directory}: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

def search_test_by_name(target_directory: str, test_name: str, fuzzy_match: bool = True, 
                       tool_context: ToolContext | None = None) -> Dict[str, Any]:
    """Search for a specific test by name in the codebase."""
    try:
        if not os.path.exists(target_directory):
            return {"error": f"Target directory does not exist: {target_directory}"}
        
        logger.info(f"Searching for test '{test_name}' in: {target_directory}")
        matches = []
        
        # Get test file discovery first
        test_files_result = discover_test_files(target_directory, tool_context)
        if "error" in test_files_result:
            return test_files_result
        
        test_files = test_files_result.get("discovered_test_files", [])
        
        for test_file in test_files:
            try:
                with open(test_file["absolute_path"], 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Look for exact matches first
                if _find_test_in_content(content, test_name, exact=True):
                    matches.append({
                        "file_path": test_file["file_path"],
                        "absolute_path": test_file["absolute_path"],
                        "match_type": "exact",
                        "language": test_file["language"],
                        "test_functions": _extract_test_functions_from_content(content, test_file["language"])
                    })
                elif fuzzy_match and _find_test_in_content(content, test_name, exact=False):
                    matches.append({
                        "file_path": test_file["file_path"],
                        "absolute_path": test_file["absolute_path"],
                        "match_type": "fuzzy",
                        "language": test_file["language"],
                        "test_functions": _extract_test_functions_from_content(content, test_file["language"])
                    })
                    
            except Exception as e:
                logger.warning(f"Error reading test file {test_file['file_path']}: {e}")
                continue
        
        return {
            "search_term": test_name,
            "matches_found": matches,
            "total_matches": len(matches),
            "fuzzy_matching_enabled": fuzzy_match
        }
        
    except Exception as e:
        error_msg = f"Error searching for test '{test_name}' in {target_directory}: {str(e)}"
        logger.error(error_msg)
        return {"error": error_msg}

def save_analysis_report(report_data: Dict[str, Any], target_directory: str, 
                        tool_context: ToolContext | None = None) -> Dict[str, str]:
    """Save the analysis report to a JSON file in the project_test_summarizer directory."""
    try:
        # Save in the project_test_summarizer directory, not the target project
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_file = os.path.join(current_dir, REPORT_OUTPUT_FILE)
        
        # Add metadata to the report
        enhanced_report = {
            "metadata": {
                "analyzed_project": target_directory,
                "analysis_timestamp": __import__('datetime').datetime.now().isoformat(),
                "analyzer_version": "1.0.0"
            },
            "analysis_results": report_data
        }
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(enhanced_report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Analysis report saved to: {output_file}")
        return {
            "status": "success",
            "output_file": output_file,
            "file_size": os.path.getsize(output_file)
        }
        
    except Exception as e:
        error_msg = f"Error saving analysis report: {str(e)}"
        logger.error(error_msg)
        return {"status": "error", "message": error_msg}

# --- Helper Functions ---

def _extract_tests_from_text(content: str) -> List[Dict[str, Any]]:
    """Extract test names from plain text content using regex patterns."""
    tests = []
    
    # Common test name patterns
    patterns = [
        r'test_(\w+)',           # Python pytest style
        r'def test_(\w+)',       # Python function definitions
        r'class Test(\w+)',      # Python test classes
        r'@Test.*?(\w+)',        # Java @Test annotations
        r'it\(["\']([^"\']+)',   # JavaScript/TypeScript it() blocks
        r'describe\(["\']([^"\']+)', # JavaScript/TypeScript describe blocks
        r'test\(["\']([^"\']+)', # JavaScript/TypeScript test() blocks
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            test_name = match.group(1)
            tests.append({
                "test_name": test_name,
                "full_name": test_name,
                "status": "unknown",
                "extraction_method": "regex_text"
            })
    
    return tests

def _extract_tests_from_json(json_data: Any) -> List[Dict[str, Any]]:
    """Extract test names from JSON test report data."""
    tests = []
    
    # Handle different JSON structures
    if isinstance(json_data, dict):
        # Jest/Vitest style
        if "testResults" in json_data:
            for test_result in json_data["testResults"]:
                if "assertionResults" in test_result:
                    for assertion in test_result["assertionResults"]:
                        tests.append({
                            "test_name": assertion.get("title", ""),
                            "full_name": assertion.get("fullName", assertion.get("title", "")),
                            "status": assertion.get("status", "unknown"),
                            "execution_time": assertion.get("duration", ""),
                            "extraction_method": "json_jest"
                        })
        
        # Generic test results structure
        elif "tests" in json_data:
            for test in json_data["tests"]:
                tests.append({
                    "test_name": test.get("name", ""),
                    "full_name": test.get("fullName", test.get("name", "")),
                    "status": test.get("status", "unknown"),
                    "extraction_method": "json_generic"
                })
    
    return tests

def _extract_tests_from_html(content: str) -> List[Dict[str, Any]]:
    """Extract test names from HTML test report content."""
    tests = []
    
    # Common HTML report patterns
    patterns = [
        r'<td[^>]*class="test[^"]*"[^>]*>([^<]+)',
        r'<span[^>]*class="test[^"]*"[^>]*>([^<]+)',
        r'<div[^>]*class="test[^"]*"[^>]*>([^<]+)',
        r'data-test-name="([^"]+)"',
        r'id="test_([^"]+)"'
    ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE)
        for match in matches:
            test_name = match.group(1).strip()
            if test_name and len(test_name) > 2:  # Filter out very short matches
                tests.append({
                    "test_name": test_name,
                    "full_name": test_name,
                    "status": "unknown",
                    "extraction_method": "html_parsing"
                })
    
    return tests

def _detect_language_from_extension(file_path: str) -> str:
    """Detect programming language from file extension."""
    ext = os.path.splitext(file_path)[1].lower()
    language_map = {
        '.py': 'python',
        '.java': 'java',
        '.kt': 'kotlin',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.cs': 'csharp',
        '.cpp': 'cpp',
        '.c': 'c',
        '.rb': 'ruby',
        '.go': 'go',
        '.rs': 'rust',
        '.php': 'php'
    }
    return language_map.get(ext, 'unknown')

def _find_test_in_content(content: str, test_name: str, exact: bool = True) -> bool:
    """Find test name in file content."""
    if exact:
        # Look for exact matches with common test patterns
        patterns = [
            rf'\bdef\s+{re.escape(test_name)}\b',  # Python function
            rf'\btest_{re.escape(test_name)}\b',   # Python pytest style
            rf'\b{re.escape(test_name)}_test\b',   # Python test suffix
            rf'\bclass\s+{re.escape(test_name)}\b', # Test class
            rf'@Test.*{re.escape(test_name)}',     # Java @Test
            rf'it\s*\(\s*["\'].*{re.escape(test_name)}.*["\']', # JS/TS it()
            rf'test\s*\(\s*["\'].*{re.escape(test_name)}.*["\']' # JS/TS test()
        ]
        return any(re.search(pattern, content, re.IGNORECASE) for pattern in patterns)
    else:
        # Fuzzy matching - check if test_name appears anywhere
        return test_name.lower() in content.lower()

def _extract_test_functions_from_content(content: str, language: str) -> List[Dict[str, str]]:
    """Extract test function definitions from content based on language."""
    functions = []
    
    if language == 'python':
        # Python test functions
        patterns = [
            r'def\s+(test_\w+)\s*\([^)]*\):\s*"""([^"]*?)"""',  # With docstring
            r'def\s+(test_\w+)\s*\([^)]*\):',                   # Without docstring
            r'class\s+(Test\w+).*?:'                            # Test classes
        ]
    elif language == 'java':
        # Java test methods
        patterns = [
            r'@Test.*?public\s+void\s+(\w+)\s*\([^)]*\)',
            r'@Test.*?(\w+)\s*\([^)]*\)'
        ]
    elif language in ['javascript', 'typescript']:
        # JavaScript/TypeScript test functions
        patterns = [
            r'it\s*\(\s*["\']([^"\']+)["\']',
            r'test\s*\(\s*["\']([^"\']+)["\']',
            r'describe\s*\(\s*["\']([^"\']+)["\']'
        ]
    else:
        # Generic patterns
        patterns = [
            r'test\w*\s+(\w+)',
            r'(\w*test\w*)\s*\('
        ]
    
    for pattern in patterns:
        matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
        for match in matches:
            func_name = match.group(1)
            functions.append({
                "function_name": func_name,
                "language": language,
                "line_context": match.group(0)
            })
    
    return functions 