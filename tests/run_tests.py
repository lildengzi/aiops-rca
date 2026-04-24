"""
测试运行脚本 - 运行所有模块的测试
使用方法：
    python run_tests.py              # 运行所有测试
    python run_tests.py --module data_loader  # 运行指定模块测试
    python run_tests.py --knowledge    # 只运行知识库测试
    python run_tests.py --workflow     # 只运行工作流测试
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pytest


def main():
    parser = argparse.ArgumentParser(description="AIOps RCA 测试运行器")
    parser.add_argument("--module", type=str, help="指定测试模块 (data_loader, anomaly_detection, etc.)")
    parser.add_argument("--knowledge", action="store_true", help="只运行知识库测试")
    parser.add_argument("--workflow", action="store_true", help="只运行工作流测试")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    parser.add_argument("--tb", type=str, default="short", help="traceback样式 (short, long, line, native)")

    args = parser.parse_args()

    pytest_args = ["tests/", f"--tb={args.tb}"]

    if args.verbose:
        pytest_args.append("-v")

    if args.knowledge:
        pytest_args = ["tests/test_knowledge_base.py", f"--tb={args.tb}"]
        if args.verbose:
            pytest_args.append("-v")
    elif args.workflow:
        pytest_args = ["tests/test_workflow.py", f"--tb={args.tb}"]
        if args.verbose:
            pytest_args.append("-v")
    elif args.module:
        module_name = args.module.lower()
        test_file = f"tests/test_{module_name}.py"
        if os.path.exists(test_file):
            pytest_args = [test_file, f"--tb={args.tb}"]
            if args.verbose:
                pytest_args.append("-v")
        else:
            print(f"错误: 找不到测试文件 {test_file}")
            print(f"可用的模块测试: data_loader, anomaly_detection, knowledge_base, workflow, tools")
            return 1

    print("=" * 60)
    print("  AIOps RCA 系统测试")
    print("=" * 60)
    print(f"\n运行: pytest {' '.join(pytest_args)}\n")

    return pytest.main(pytest_args)


if __name__ == "__main__":
    sys.exit(main())
