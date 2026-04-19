"""
Test Suite Runner Script

Run this script to execute the complete test suite for the Leave Management System.

Usage:
    python run_tests.py                 # Run all tests
    python run_tests.py --tc04          # Run specific test case
    python run_tests.py --coverage      # Run with coverage report
    python run_tests.py --parallel      # Run in parallel
    python run_tests.py --quick         # Quick run (fast tests only)
"""

import sys
import subprocess
import argparse
from pathlib import Path


class TestRunner:
    """Execute test suite with various options."""
    
    def __init__(self):
        self.test_dir = Path(__file__).parent
        self.project_root = self.test_dir.parent
        
    def run_command(self, cmd, description):
        """Run a shell command with status reporting."""
        print(f"\n{'='*70}")
        print(f">>> {description}")
        print(f"{'='*70}")
        print(f"Command: {' '.join(cmd)}\n")
        
        result = subprocess.run(cmd, cwd=str(self.test_dir))
        return result.returncode == 0
    
    def run_all_tests(self):
        """Run all tests."""
        cmd = [sys.executable, "-m", "pytest", "-v"]
        return self.run_command(cmd, "Running ALL TESTS")
    
    def run_specific_case(self, tc_number):
        """Run specific test case."""
        marker = f"tc{tc_number:02d}"
        cmd = [sys.executable, "-m", "pytest", "-v", "-m", marker]
        return self.run_command(cmd, f"Running Test Case TC-{tc_number:02d}")
    
    def run_with_coverage(self):
        """Run all tests with coverage report."""
        cmd = [
            sys.executable, "-m", "pytest", "-v",
            "--cov=..",
            "--cov-report=html",
            "--cov-report=term-missing"
        ]
        return self.run_command(cmd, "Running tests WITH COVERAGE")
    
    def run_parallel(self):
        """Run tests in parallel."""
        cmd = [sys.executable, "-m", "pytest", "-v", "-n", "auto"]
        return self.run_command(cmd, "Running tests IN PARALLEL")
    
    def run_fast_only(self):
        """Run fast tests only."""
        cmd = [sys.executable, "-m", "pytest", "-v", "-m", "not slow"]
        return self.run_command(cmd, "Running FAST TESTS ONLY")
    
    def run_data_pipeline(self):
        """Run data pipeline tests (TC-01 to TC-03)."""
        cmd = [
            sys.executable, "-m", "pytest", "-v",
            "-m", "tc01 or tc02 or tc03"
        ]
        return self.run_command(cmd, "Running DATA PIPELINE tests (TC-01 to TC-03)")
    
    def run_model_pipeline(self):
        """Run model pipeline tests (TC-04 to TC-05)."""
        cmd = [
            sys.executable, "-m", "pytest", "-v",
            "-m", "tc04 or tc05"
        ]
        return self.run_command(cmd, "Running MODEL PIPELINE tests (TC-04 to TC-05)")
    
    def run_validation(self):
        """Run validation tests (TC-08 to TC-10)."""
        cmd = [
            sys.executable, "-m", "pytest", "-v",
            "-m", "tc08 or tc09 or tc10"
        ]
        return self.run_command(cmd, "Running VALIDATION tests (TC-08 to TC-10)")
    
    def run_dashboard(self):
        """Run dashboard tests (TC-06 to TC-07)."""
        cmd = [sys.executable, "-m", "pytest", "-v", "test_06_07_dashboard.py"]
        return self.run_command(cmd, "Running DASHBOARD tests (TC-06 & TC-07)")


def main():
    """Parse arguments and run tests."""
    parser = argparse.ArgumentParser(
        description="Run Leave Management System test suite",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_tests.py              # Run all tests
  python run_tests.py --tc04       # Run TC-04 only
  python run_tests.py --coverage   # Run with coverage
  python run_tests.py --parallel   # Run in parallel
  python run_tests.py --all        # Run everything
        """
    )
    
    parser.add_argument("--all", action="store_true", help="Run all tests (default)")
    parser.add_argument("--tc01", action="store_true", help="Run TC-01 (Data Loading)")
    parser.add_argument("--tc02", action="store_true", help="Run TC-02 (Data Cleaning)")
    parser.add_argument("--tc03", action="store_true", help="Run TC-03 (Feature Engineering)")
    parser.add_argument("--tc04", action="store_true", help="Run TC-04 (Model Training)")
    parser.add_argument("--tc05", action="store_true", help="Run TC-05 (Forecasting)")
    parser.add_argument("--tc06-07", action="store_true", help="Run TC-06 & TC-07 (Dashboard)")
    parser.add_argument("--tc08", action="store_true", help="Run TC-08 (Model Accuracy)")
    parser.add_argument("--tc09", action="store_true", help="Run TC-09 (Data Leakage)")
    parser.add_argument("--tc10", action="store_true", help="Run TC-10 (Confidence Intervals)")
    
    parser.add_argument("--data-pipeline", action="store_true", help="Run TC-01 to TC-03")
    parser.add_argument("--model-pipeline", action="store_true", help="Run TC-04 to TC-05")
    parser.add_argument("--validation", action="store_true", help="Run TC-08 to TC-10")
    parser.add_argument("--dashboard", action="store_true", help="Run TC-06 & TC-07")
    
    parser.add_argument("--coverage", action="store_true", help="Run with coverage report")
    parser.add_argument("--parallel", action="store_true", help="Run in parallel")
    parser.add_argument("--quick", action="store_true", help="Run fast tests only")
    
    args = parser.parse_args()
    
    runner = TestRunner()
    success = True
    
    # Print banner
    print("\n" + "="*70)
    print("LEAVE MANAGEMENT SYSTEM - TEST SUITE RUNNER")
    print("="*70)
    
    # Check if any specific tests selected
    if args.tc01:
        success = runner.run_specific_case(1) and success
    elif args.tc02:
        success = runner.run_specific_case(2) and success
    elif args.tc03:
        success = runner.run_specific_case(3) and success
    elif args.tc04:
        success = runner.run_specific_case(4) and success
    elif args.tc05:
        success = runner.run_specific_case(5) and success
    elif args.tc06_07:
        success = runner.run_dashboard() and success
    elif args.tc08:
        success = runner.run_specific_case(8) and success
    elif args.tc09:
        success = runner.run_specific_case(9) and success
    elif args.tc10:
        success = runner.run_specific_case(10) and success
    elif args.data_pipeline:
        success = runner.run_data_pipeline() and success
    elif args.model_pipeline:
        success = runner.run_model_pipeline() and success
    elif args.validation:
        success = runner.run_validation() and success
    elif args.dashboard:
        success = runner.run_dashboard() and success
    elif args.coverage:
        success = runner.run_with_coverage() and success
    elif args.parallel:
        success = runner.run_parallel() and success
    elif args.quick:
        success = runner.run_fast_only() and success
    else:
        # Default: run all tests
        success = runner.run_all_tests() and success
    
    # Print summary
    print("\n" + "="*70)
    if success:
        print("✓ TEST SUITE COMPLETED SUCCESSFULLY")
        print("="*70)
        return 0
    else:
        print("✗ TEST SUITE FAILED")
        print("="*70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
