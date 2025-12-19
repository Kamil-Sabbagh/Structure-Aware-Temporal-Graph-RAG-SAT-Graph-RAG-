#!/bin/bash
# Script to set up and start Neo4j with APOC

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_ROOT/docker"

echo "=== SAT-Graph RAG: Neo4j Setup ==="

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "Error: Docker is not running. Please start Docker first."
    exit 1
fi

cd "$DOCKER_DIR"

# Start Neo4j
echo "Starting Neo4j container..."
docker-compose up -d

# Wait for Neo4j to be ready
echo "Waiting for Neo4j to be ready..."
sleep 30

# Verify connection
echo "Verifying Neo4j connection..."
if docker exec sat-graph-neo4j cypher-shell -u neo4j -p satgraphrag123 "RETURN 1 AS test" > /dev/null 2>&1; then
    echo "✓ Neo4j is running and accessible"
else
    echo "✗ Could not connect to Neo4j. Check the logs with: docker logs sat-graph-neo4j"
    exit 1
fi

# Verify APOC
echo "Verifying APOC installation..."
if docker exec sat-graph-neo4j cypher-shell -u neo4j -p satgraphrag123 "RETURN apoc.version() AS version" > /dev/null 2>&1; then
    echo "✓ APOC plugin is installed"
else
    echo "✗ APOC plugin is not installed"
    echo "  You may need to download it manually:"
    echo "  curl -L https://github.com/neo4j/apoc/releases/download/5.15.0/apoc-5.15.0-core.jar -o docker/neo4j/plugins/apoc-5.15.0-core.jar"
    exit 1
fi

echo ""
echo "=== Neo4j Setup Complete ==="
echo "Neo4j Browser: http://localhost:7474"
echo "Bolt URI: bolt://localhost:7687"
echo "Username: neo4j"
echo "Password: satgraphrag123"

