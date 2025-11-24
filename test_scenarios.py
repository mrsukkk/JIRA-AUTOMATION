"""
Test scenarios for JIRA Agent Chatbot
Run these to verify the system works correctly.
"""
import os
import sys
import time
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

load_dotenv()

def print_test_header(test_name: str):
    """Print formatted test header."""
    print("\n" + "="*60)
    print(f"TEST: {test_name}")
    print("="*60)


def test_environment_setup():
    """Test 1: Verify environment variables are set."""
    print_test_header("Environment Setup")
    
    required_vars = [
        "GOOGLE_API_KEY",
        "JIRA_BASE_URL",
        "JIRA_USERNAME",
        "JIRA_PAT"
    ]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
        else:
            # Mask sensitive values
            masked = value[:4] + "..." + value[-4:] if len(value) > 8 else "***"
            print(f"✅ {var}: {masked}")
    
    if missing:
        print(f"❌ Missing environment variables: {', '.join(missing)}")
        print("   Please create a .env file with these variables.")
        return False
    
    print("✅ All environment variables are set!")
    return True


def test_imports():
    """Test 2: Verify all imports work."""
    print_test_header("Module Imports")
    
    try:
        from models.llm_config import LLMConfig
        print("✅ LLM config imported")
        
        from graphs.jira_agent_graph import app
        print("✅ LangGraph workflow imported")
        
        from approval.approval_manager import approval_manager
        print("✅ Approval manager imported")
        
        from tools.jira_tool import get_jira_client
        print("✅ JIRA tools imported")
        
        from web.app import web_app
        print("✅ Web app imported")
        
        print("✅ All imports successful!")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False


def test_jira_connection():
    """Test 3: Verify JIRA connection."""
    print_test_header("JIRA Connection")
    
    try:
        from tools.jira_tool import get_jira_client
        
        print("Attempting to connect to JIRA...")
        jira = get_jira_client()
        
        # Test connection by getting current user
        user = jira.current_user()
        print(f"✅ Connected to JIRA successfully!")
        print(f"   Current user: {user}")
        
        return True
    except Exception as e:
        print(f"❌ JIRA connection failed: {e}")
        print("   Please check your JIRA credentials in .env file")
        return False


def test_llm_initialization():
    """Test 4: Verify LLM initialization."""
    print_test_header("LLM Initialization")
    
    try:
        from models.llm_config import LLMConfig
        
        print("Initializing LLM...")
        llm = LLMConfig.get_llm()
        
        # Test with a simple prompt
        from langchain_core.messages import HumanMessage
        response = llm.invoke([HumanMessage(content="Say 'Hello' if you can read this.")])
        
        print(f"✅ LLM initialized successfully!")
        print(f"   Response: {response.content[:100]}...")
        
        return True
    except Exception as e:
        print(f"❌ LLM initialization failed: {e}")
        print("   Please check your GOOGLE_API_KEY in .env file")
        return False


def test_approval_system():
    """Test 5: Verify approval system."""
    print_test_header("Approval System")
    
    try:
        from approval.approval_manager import approval_manager, ApprovalStatus
        
        # Create a test approval
        approval = approval_manager.create_approval_request(
            operation_type="test_operation",
            preview={"test": "data"},
            description="Test approval request"
        )
        
        print(f"✅ Approval request created: {approval.request_id}")
        
        # Test approval
        if approval_manager.approve(approval.request_id):
            print("✅ Approval system working correctly!")
            return True
        else:
            print("❌ Approval failed")
            return False
            
    except Exception as e:
        print(f"❌ Approval system test failed: {e}")
        return False


def test_read_operations():
    """Test 6: Verify read operations."""
    print_test_header("Read Operations")
    
    try:
        from tools.jira_tool import fetch_statuses
        
        print("Fetching JIRA statuses...")
        statuses = fetch_statuses()
        
        print(f"✅ Read operations working!")
        print(f"   Found {len(statuses)} statuses")
        print(f"   Sample statuses: {', '.join(statuses[:5])}")
        
        return True
    except Exception as e:
        print(f"❌ Read operations test failed: {e}")
        return False


def test_web_server():
    """Test 7: Verify web server can start."""
    print_test_header("Web Server")
    
    try:
        from web.app import web_app
        
        print("✅ Web app created successfully!")
        print("   Server can be started with: python run_web.py")
        
        return True
    except Exception as e:
        print(f"❌ Web server test failed: {e}")
        return False


def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("JIRA AGENT CHATBOT - TEST SUITE")
    print("="*60)
    
    tests = [
        ("Environment Setup", test_environment_setup),
        ("Module Imports", test_imports),
        ("JIRA Connection", test_jira_connection),
        ("LLM Initialization", test_llm_initialization),
        ("Approval System", test_approval_system),
        ("Read Operations", test_read_operations),
        ("Web Server", test_web_server),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} crashed: {e}")
            results.append((test_name, False))
        time.sleep(0.5)  # Small delay between tests
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready to use.")
        print("\nNext steps:")
        print("1. Start the web server: python run_web.py")
        print("2. Open browser: http://localhost:8000")
        print("3. Register and start chatting!")
    else:
        print("\n⚠️  Some tests failed. Please fix the issues above.")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)

