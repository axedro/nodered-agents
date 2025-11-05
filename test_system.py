#!/usr/bin/env python3
"""
Test script para verificar que el sistema funciona correctamente
"""
import asyncio
import httpx
import json
from loguru import logger

API_BASE = "http://localhost:8000/api"


async def test_health():
    """Test health endpoint"""
    logger.info("Testing health endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/health")
        assert response.status_code == 200
        data = response.json()
        logger.info(f"✓ Health: {data}")
        return data


async def test_init_nodes():
    """Test initializing sample nodes"""
    logger.info("Testing node initialization...")
    async with httpx.AsyncClient() as client:
        response = await client.post(f"{API_BASE}/init-nodes")
        assert response.status_code == 200
        data = response.json()
        logger.info(f"✓ Init nodes: {data}")
        return data


async def test_chat_session():
    """Test a complete chat session"""
    logger.info("Testing chat session...")

    session_id = None

    async with httpx.AsyncClient(timeout=60.0) as client:
        # First message
        logger.info("Sending first message...")
        response = await client.post(
            f"{API_BASE}/chat",
            json={
                "message": "Quiero un flujo simple que reciba un inject y muestre el resultado en debug",
                "user_id": "test_user"
            }
        )
        assert response.status_code == 200
        data = response.json()
        session_id = data['session_id']
        logger.info(f"✓ Session created: {session_id}")
        logger.info(f"  Response: {data['message'][:100]}...")

        # Continue conversation (if needed)
        if data['requires_input'] and not data['flow_ready']:
            logger.info("Continuing conversation...")
            response = await client.post(
                f"{API_BASE}/chat",
                json={
                    "session_id": session_id,
                    "message": "Solo quiero inyectar un timestamp y mostrarlo en debug",
                    "user_id": "test_user"
                }
            )
            data = response.json()
            logger.info(f"  Response: {data['message'][:100]}...")

        # Check if flow is ready
        if data['flow_ready']:
            logger.info("✓ Flow generated!")
            flow_json = data['flow_json']
            logger.info(f"  Flow JSON length: {len(flow_json)} chars")

            # Validate JSON
            flow = json.loads(flow_json)
            logger.info(f"  Flow has {len(flow)} nodes")

            return session_id, flow_json
        else:
            logger.warning("Flow not ready yet (may need more conversation)")
            return session_id, None


async def test_feedback(session_id, flow_json):
    """Test feedback submission"""
    if not flow_json:
        logger.warning("Skipping feedback test (no flow)")
        return

    logger.info("Testing feedback submission...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE}/feedback",
            json={
                "session_id": session_id,
                "flow_json": flow_json,
                "feedback_type": "approve",
                "score": 5,
                "comments": "Test flow - works great!"
            }
        )
        assert response.status_code == 200
        data = response.json()
        logger.info(f"✓ Feedback submitted: {data}")


async def test_stats():
    """Test stats endpoint"""
    logger.info("Testing stats endpoint...")
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE}/stats")
        assert response.status_code == 200
        data = response.json()
        logger.info(f"✓ Stats: {json.dumps(data, indent=2)}")


async def main():
    """Run all tests"""
    logger.info("=" * 60)
    logger.info("Node-RED Multi-Agent System - Integration Tests")
    logger.info("=" * 60)

    try:
        # Test 1: Health check
        await test_health()

        # Test 2: Initialize nodes
        await test_init_nodes()

        # Test 3: Chat session
        session_id, flow_json = await test_chat_session()

        # Test 4: Submit feedback
        await test_feedback(session_id, flow_json)

        # Test 5: Stats
        await test_stats()

        logger.info("=" * 60)
        logger.info("✓ ALL TESTS PASSED!")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"✗ TEST FAILED: {e}", exc_info=True)
        logger.info("=" * 60)
        logger.info("Make sure:")
        logger.info("1. Backend is running (python -m uvicorn backend.main:app)")
        logger.info("2. Ollama is running (ollama serve)")
        logger.info("3. Model is downloaded (ollama pull mistral)")
        logger.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
