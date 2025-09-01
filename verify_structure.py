#!/usr/bin/env python3
"""Verify the onepage package structure and basic imports."""

import sys
from pathlib import Path

def verify_structure():
    """Verify package structure is correct."""
    
    print("Verifying onepage package structure...")
    print("=" * 50)
    
    # Check main package files
    required_files = [
        "onepage/__init__.py",
        "onepage/core/__init__.py",
        "onepage/core/models.py",
        "onepage/core/config.py", 
        "onepage/api/__init__.py",
        "onepage/api/wikidata.py",
        "onepage/api/wikipedia.py",
        "onepage/api/fetcher.py",
        "onepage/processing/__init__.py",
        "onepage/processing/text.py",
        "onepage/processing/translation.py",
        "onepage/processing/alignment.py",
        "onepage/processing/references.py",
        "onepage/processing/builder.py",
        "onepage/renderers/__init__.py",
        "onepage/renderers/wikitext.py",
        "onepage/renderers/html.py",
        "onepage/renderers/attribution.py",
        "onepage/cli/__init__.py",
        "onepage/cli/main.py",
        "pyproject.toml",
        "README.md",
        "onepage.yaml",
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
        else:
            print(f"✓ {file_path}")
    
    if missing_files:
        print(f"\n❌ Missing files:")
        for file_path in missing_files:
            print(f"  - {file_path}")
        return False
    
    print(f"\n✓ All {len(required_files)} required files found!")
    
    # Test basic imports (without heavy dependencies)
    print("\nTesting basic imports...")
    
    try:
        # Test data models
        from onepage.core.models import Entity, Claim, Fact, Reference
        print("✓ Core models import successfully")
        
        # Test basic entity creation
        entity = Entity(qid="Q1058", labels={"en": "Test"})
        print(f"✓ Can create Entity: {entity.qid}")
        
        # Test claim creation
        claim = Claim(id="c1", text="Test claim", lang="en")
        print(f"✓ Can create Claim: {claim.id}")
        
        # Test fact creation
        fact = Fact(id="f1", property="P39", value="test")
        print(f"✓ Can create Fact: {fact.id}")
        
        print("\n✓ Basic functionality verified!")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def check_dependencies():
    """Check if required dependencies are available."""
    print("\nChecking dependencies...")
    
    dependencies = [
        ("click", "CLI framework"),
        ("requests", "HTTP requests"),
        ("yaml", "YAML configuration"),
        ("wikitextparser", "Wikitext parsing"),
        ("sentence_transformers", "Sentence embeddings"),
    ]
    
    available = []
    missing = []
    
    for dep, description in dependencies:
        try:
            __import__(dep)
            available.append((dep, description))
            print(f"✓ {dep} - {description}")
        except ImportError:
            missing.append((dep, description))
            print(f"❌ {dep} - {description} (missing)")
    
    if missing:
        print(f"\nTo install missing dependencies:")
        print("pip install -r requirements.txt")
        print("\nOr install manually:")
        for dep, desc in missing:
            print(f"pip install {dep}")
    
    return len(missing) == 0


if __name__ == "__main__":
    structure_ok = verify_structure()
    deps_ok = check_dependencies()
    
    if structure_ok and deps_ok:
        print("\n" + "=" * 50)
        print("🎉 onepage package is ready to use!")
        print("\nTry running:")
        print("  python -m onepage.cli.main --help")
        print("  python example.py")
        sys.exit(0)
    else:
        print("\n" + "=" * 50) 
        print("⚠ Issues found. Please resolve them before using onepage.")
        sys.exit(1)