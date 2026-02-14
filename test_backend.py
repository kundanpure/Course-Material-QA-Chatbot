"""
Backend Component Test Suite - Simple Version
Tests: Database, LLM, Agents
"""
import asyncio
import sys
sys.path.insert(0, '.')

async def test_database():
    """Test NeonDB PostgreSQL connection"""
    print("\n[DATABASE] Testing connection...")
    try:
        from db.session import AsyncSessionLocal
        from sqlalchemy import text
        
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT version()"))
            version = result.scalar_one()
            print("[DATABASE] SUCCESS - Connected!")
            print(f"[DATABASE] PostgreSQL version: {version[:60]}...")
            return True
    except Exception as e:
        print(f"[DATABASE] FAILED: {e}")
        return False


async def test_llm():
    """Test Gemini LLM integration"""
    print("\n[GEMINI LLM] Testing integration...")
    try:
        from services.llm_router import llm_router
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Explain machine learning in one sentence."}
        ]
        
        response = await llm_router.chat(messages=messages, temperature=0.7, max_tokens=100)
        
        print(f"[GEMINI LLM] SUCCESS!")
        print(f"[GEMINI LLM] Response: {response['content'][:100]}...")
        print(f"[GEMINI LLM] Tokens used: {response['tokens_used']}")
        print(f"[GEMINI LLM] Model: {response['model']}")
        return True
    except Exception as e:
        print(f"[GEMINI LLM] FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_agents():
    """Test agent pipeline"""
    print("\n[AGENTS] Testing agent pipeline...")
    try:
        from agents.query_classifier import QueryClassifier
        from agents.answer_composer import answer_composer
        
        # Test query classifier
        classifier = QueryClassifier()
        query_type = await classifier.classify("What is supervised learning?")
        print(f"[AGENTS] Query Classifier working! Type: {query_type}")
        
        # Test answer composer with mock context
        mock_context = [
            {
                "text": "Supervised learning uses labeled data for training.",
                "metadata": {"source": "ML_Textbook.pdf", "page": 15},
                "score": 0.92
            }
        ]
        
        result = await answer_composer.compose(
            query="What is supervised learning?",
            context_chunks=mock_context,
            query_type=query_type
        )
        
        print(f"[AGENTS] Answer Composer working!")
        print(f"[AGENTS] Answer: {result['answer'][:100]}...")
        return True
    except Exception as e:
        print(f"[AGENTS] FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests"""
    print("="*60)
    print("BACKEND COMPONENT TEST SUITE")
    print("="*60)
    
    results = {}
    results['database'] = await test_database()
    results['llm'] = await test_llm()
    results['agents'] = await test_agents()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for component, passed in results.items():
        status = "PASSED" if passed else "FAILED"
        print(f"{component.upper():12} : {status}")
    
    print("="*60)
    
    if all(results.values()):
        print("\nSUCCESS! All critical components working!")
        print("\nNext steps:")
        print("  1. Start server: python main.py")
        print("  2. Visit: http://localhost:8000/api/docs")
    else:
        print("\nSOME TESTS FAILED - Check errors above")


if __name__ == "__main__":
    asyncio.run(main())
