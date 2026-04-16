#!/usr/bin/env python3
"""Verify the wikifuse package structure and basic imports."""

import sys
from pathlib import Path

def verify_structure():
    """Verify package structure is correct."""
    
    print("Verifying wikifuse package structure...")
    print("=" * 50)
    
    # Check main package files
    required_files = [
        "wikifuse/__init__.py",
        "wikifuse/core/__init__.py",
        "wikifuse/core/models.py",
        "wikifuse/core/config.py", 
        "wikifuse/api/__init__.py",
        "wikifuse/api/wikidata.py",
        "wikifuse/api/wikipedia.py",
        "wikifuse/api/fetcher.py",
        "wikifuse/processing/__init__.py",
        "wikifuse/processing/text.py",
        "wikifuse/processing/translation.py",
        "wikifuse/processing/alignment.py",
        "wikifuse/processing/references.py",
        "wikifuse/processing/builder.py",
        "wikifuse/renderers/__init__.py",
        "wikifuse/renderers/wikitext.py",
        "wikifuse/renderers/html.py",
        "wikifuse/renderers/attribution.py",
        "wikifuse/cli/__init__.py",
        "wikifuse/cli/main.py",
        "pyproject.toml",
        "README.md",
        "wikifuse.yaml",
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
        from wikifuse.core.models import Entity, Claim, Fact, Reference
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
        print("🎉 wikifuse package is ready to use!")
        print("\nTry running:")
        print("  python -m wikifuse.cli.main --help")
        print("  python example.py")
        sys.exit(0)
    else:
        print("\n" + "=" * 50) 
        print("⚠ Issues found. Please resolve them before using wikifuse.")
        sys.exit(1)