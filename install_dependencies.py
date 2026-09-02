#!/usr/bin/env python3
"""Installation and verification script for BIOCORE AI dependencies."""

import sys
import subprocess
import os

def run_command(cmd, description):
    """Run a shell command and report results."""
    print(f"\n{'='*60}")
    print(f"📦 {description}")
    print(f"{'='*60}")
    print(f"Running: {cmd}")
    
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    
    return result.returncode == 0

def main():
    """Main installation routine."""
    
    print("\n" + "="*60)
    print("🚀 BIOCORE AI - DEPENDENCY INSTALLATION")
    print("="*60)
    
    # Step 1: Upgrade pip
    print("\n[1/3] Upgrading pip...")
    run_command(f"{sys.executable} -m pip install --upgrade pip", "Upgrade pip")

    # Step 2: Install core dependencies
    print("\n[2/3] Installing core dependencies...")
    core_deps = [
        "streamlit>=1.25.0",
        "numpy>=1.20.0",
        "scipy>=1.7.0",
        "pandas>=1.3.0",
        "matplotlib>=3.4.0",
        "plotly>=5.0.0",
        "scikit-learn>=1.0.0",
        "Pillow>=8.0.0",
    ]
    
    for dep in core_deps:
        run_command(f"{sys.executable} -m pip install --upgrade {dep}", f"Install {dep}")
    
    # Step 3: Install AI dependencies
    print("\n[3/3] Installing AI dependencies...")
    ai_deps = [
        "anthropic>=0.40.0",
        "sqlalchemy>=2.0.0",
        "shap>=0.42.0",
        "lime>=0.2.0",
    ]
    
    for dep in ai_deps:
        run_command(f"{sys.executable} -m pip install --upgrade {dep}", f"Install {dep}")
    
    # Verification
    print("\n" + "="*60)
    print("✅ VERIFICATION")
    print("="*60)
    
    packages_to_check = [
        ("streamlit", "st"),
        ("numpy", "np"),
        ("scipy", None),
        ("pandas", "pd"),
        ("matplotlib", "plt"),
        ("plotly", None),
        ("sklearn", None),
        ("PIL", "Image"),
        ("anthropic", None),
        ("sqlalchemy", None),
    ]
    
    failed = []
    
    for package, alias in packages_to_check:
        try:
            if alias:
                exec(f"import {package} as {alias}")
            else:
                exec(f"import {package}")
            print(f"✅ {package:20} - OK")
        except ImportError as e:
            print(f"❌ {package:20} - FAILED: {e}")
            failed.append(package)
    
    print("\n" + "="*60)
    if failed:
        print(f"❌ {len(failed)} package(s) failed to import: {', '.join(failed)}")
    else:
        print("✅ All packages installed and verified successfully!")

    print("\n" + "="*60)
    print("📝 NEXT STEPS:")
    print("="*60)
    print("1. Set ANTHROPIC_API_KEY (get free key from https://console.anthropic.com):")
    print("   $env:ANTHROPIC_API_KEY = 'sk-your-key'  # PowerShell")
    print("   set ANTHROPIC_API_KEY=sk-your-key       # CMD")
    print("\n2. Run the app:")
    print("   streamlit run app/main.py")
    print("\n3. Explore: AI Hub → 🩺 Narrador Clínico (narrador clínico con IA real)")
    print("\n" + "="*60)

if __name__ == "__main__":
    main()
