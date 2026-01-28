#!/usr/bin/env python
"""Generate TLR-Bench (Temporal Legal Reasoning Benchmark) dataset.

Creates 100 standardized test queries across 6 task categories:
1. Point-in-Time Retrieval (30 queries)
2. Amendment Attribution (20 queries)
3. Temporal Difference (15 queries)
4. Causal-Lineage Reconstruction (10 queries)
5. Temporal Consistency (10 queries)
6. Hierarchical Impact Analysis (15 queries)

All ground truth verified from Neo4j graph database.
"""

import sys
import json
import random
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from neo4j import GraphDatabase
import os
from dotenv import load_dotenv

load_dotenv()


@dataclass
class BenchmarkQuery:
    """A single benchmark query with ground truth."""
    task: str
    query_id: str
    query: str
    difficulty: str  # 'easy', 'medium', 'hard'
    target_component: Optional[str] = None
    target_date: Optional[str] = None
    date_range: Optional[List[str]] = None
    ground_truth: Dict = None
    metadata: Dict = None


class BenchmarkGenerator:
    """Generate TLR-Bench dataset from Neo4j graph."""

    def __init__(self):
        """Initialize Neo4j connection."""
        self.driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI'),
            auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
        )

    def close(self):
        """Close Neo4j connection."""
        self.driver.close()

    def _get_articles_with_versions(self, min_versions: int = 2) -> List[Dict]:
        """Get articles that have multiple versions."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Component)-[:HAS_VERSION]->(v:CTV)
                WHERE c.component_type = 'article'
                WITH c, count(v) AS version_count
                WHERE version_count >= $min_versions
                RETURN c.component_id AS component_id,
                       version_count,
                       c.component_type AS type
                ORDER BY version_count DESC
            """, min_versions=min_versions)
            return [dict(record) for record in result]

    def _get_version_history(self, component_id: str) -> List[Dict]:
        """Get complete version history for a component."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Component {component_id: $component_id})
                      -[:HAS_VERSION]->(v:CTV)
                OPTIONAL MATCH (v)<-[:RESULTED_IN]-(a:Action)
                RETURN v.version_number AS version,
                       v.date_start AS date_start,
                       v.date_end AS date_end,
                       v.is_active AS is_active,
                       a.action_id AS amendment
                ORDER BY v.version_number
            """, component_id=component_id)
            return [dict(record) for record in result]

    def _get_text_for_version(self, component_id: str, target_date: date) -> Dict:
        """Get text content for a component at a specific date."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Component {component_id: $component_id})
                      -[:HAS_VERSION]->(v:CTV)
                WHERE v.date_start <= $target_date
                  AND (v.date_end IS NULL OR v.date_end > $target_date)
                MATCH (v)-[:EXPRESSED_IN]->(clv:CLV)-[:HAS_TEXT]->(t:TextUnit)
                RETURN v.version_number AS version,
                       t.full_text AS text,
                       t.content_hash AS text_hash,
                       t.header AS header
                LIMIT 1
            """, component_id=component_id, target_date=target_date)

            record = result.single()
            if record:
                return dict(record)
            return None

    def _sample_date_from_range(self, start: date, end: Optional[date]) -> date:
        """Sample a random date from a version's valid range."""
        if end is None:
            end = date.today()

        delta = (end - start).days
        if delta <= 0:
            return start

        random_days = random.randint(0, min(delta, 365 * 5))  # Cap at 5 years
        return start + timedelta(days=random_days)

    def _get_component_name(self, component_id: str) -> str:
        """Get human-readable name for a component."""
        # Extract article number from component_id
        # e.g., tit_08_cap_03_sec_01_art_214_art_214 -> Article 214
        parts = component_id.split('_')

        # Find 'art' followed by number
        for i, part in enumerate(parts):
            if part == 'art' and i + 1 < len(parts):
                try:
                    art_num = int(parts[i + 1])
                    return f"Article {art_num}"
                except ValueError:
                    pass

        return component_id

    def generate_point_in_time_queries(self, n_queries: int = 30) -> List[BenchmarkQuery]:
        """Generate point-in-time retrieval queries.

        Strategy:
        - Easy: Recent dates (2010-2025), 2-3 versions
        - Medium: Historical dates (1995-2010), 3-5 versions
        - Hard: Early dates (1988-1995), 5+ versions
        """
        queries = []
        articles = self._get_articles_with_versions(min_versions=2)

        # Sort by version count for difficulty assignment
        easy_articles = [a for a in articles if 2 <= a['version_count'] <= 3]
        medium_articles = [a for a in articles if 3 < a['version_count'] <= 5]
        hard_articles = [a for a in articles if a['version_count'] > 5]

        # Generate queries by difficulty
        targets = [
            ('easy', easy_articles, 10, date(2010, 1, 1), date(2025, 1, 1)),
            ('medium', medium_articles, 15, date(1995, 1, 1), date(2010, 1, 1)),
            ('hard', hard_articles, 5, date(1988, 10, 5), date(1995, 1, 1))
        ]

        query_id = 0
        for difficulty, article_pool, count, date_start, date_end in targets:
            if not article_pool:
                continue

            sample_articles = random.sample(article_pool, min(count, len(article_pool)))

            for article in sample_articles:
                component_id = article['component_id']
                versions = self._get_version_history(component_id)

                # Find a version within the target date range
                valid_versions = [
                    v for v in versions
                    if (datetime.fromisoformat(str(v['date_start'])).date() >= date_start and
                        datetime.fromisoformat(str(v['date_start'])).date() <= date_end)
                ]

                if not valid_versions:
                    continue

                # Pick a random version
                target_version = random.choice(valid_versions)
                version_start = datetime.fromisoformat(str(target_version['date_start'])).date()
                version_end = datetime.fromisoformat(str(target_version['date_end'])).date() if target_version['date_end'] else date.today()

                # Sample a date from this version's range
                target_date = self._sample_date_from_range(version_start, version_end)

                # Get text content
                text_data = self._get_text_for_version(component_id, target_date)
                if not text_data:
                    continue

                # Extract keywords from text
                text = text_data['text']
                words = text.split()
                keywords = [w.strip('.,;:') for w in words[5:10] if len(w) > 5][:3]

                query = BenchmarkQuery(
                    task='point_in_time',
                    query_id=f'pit_{query_id:03d}',
                    query=f"What did {self._get_component_name(component_id)} say on {target_date}?",
                    difficulty=difficulty,
                    target_component=component_id,
                    target_date=str(target_date),
                    ground_truth={
                        'correct_version': target_version['version'],
                        'valid_range': [str(version_start), str(version_end)],
                        'text_hash': text_data['text_hash'],
                        'must_contain': keywords,
                        'must_not_contain': ['Modified by EC', 'Added/Modified by EC']
                    },
                    metadata={
                        'total_versions': len(versions),
                        'target_version_duration_days': (version_end - version_start).days
                    }
                )

                queries.append(query)
                query_id += 1

                if len(queries) >= n_queries:
                    return queries

        return queries

    def generate_amendment_attribution_queries(self, n_queries: int = 20) -> List[BenchmarkQuery]:
        """Generate amendment attribution queries (provenance)."""
        queries = []
        articles = self._get_articles_with_versions(min_versions=2)

        query_id = 0
        for article in articles[:n_queries]:
            component_id = article['component_id']
            versions = self._get_version_history(component_id)

            # Get all amendments
            amendments = [v['amendment'] for v in versions if v['amendment']]

            if not amendments:
                continue

            difficulty = 'easy' if len(amendments) == 1 else ('medium' if len(amendments) <= 3 else 'hard')

            query = BenchmarkQuery(
                task='amendment_attribution',
                query_id=f'amend_{query_id:03d}',
                query=f"Which constitutional amendments changed {self._get_component_name(component_id)}?",
                difficulty=difficulty,
                target_component=component_id,
                ground_truth={
                    'amendments': amendments,
                    'dates': [str(v['date_start']) for v in versions if v['amendment']],
                    'chronological_order': True
                },
                metadata={
                    'total_amendments': len(amendments),
                    'total_versions': len(versions)
                }
            )

            queries.append(query)
            query_id += 1

            if len(queries) >= n_queries:
                break

        return queries

    def generate_temporal_difference_queries(self, n_queries: int = 15) -> List[BenchmarkQuery]:
        """Generate temporal difference queries (change detection)."""
        queries = []
        articles = self._get_articles_with_versions(min_versions=2)

        query_id = 0
        for article in articles[:n_queries]:
            component_id = article['component_id']
            versions = self._get_version_history(component_id)

            if len(versions) < 2:
                continue

            # Pick two versions to compare
            v1 = versions[0]
            v2 = versions[-1]  # Original vs current

            date_1 = datetime.fromisoformat(str(v1['date_start'])).date()
            date_2 = datetime.fromisoformat(str(v2['date_start'])).date()

            amendments_between = [v['amendment'] for v in versions[1:] if v['amendment']]

            difficulty = 'easy' if len(amendments_between) == 1 else ('medium' if len(amendments_between) <= 2 else 'hard')

            query = BenchmarkQuery(
                task='temporal_difference',
                query_id=f'diff_{query_id:03d}',
                query=f"What changed in {self._get_component_name(component_id)} between {date_1.year} and {date_2.year}?",
                difficulty=difficulty,
                target_component=component_id,
                date_range=[str(date_1), str(date_2)],
                ground_truth={
                    'changed': len(amendments_between) > 0,
                    'amendments_between': amendments_between,
                    'version_1': v1['version'],
                    'version_2': v2['version'],
                    'num_changes': len(amendments_between)
                },
                metadata={
                    'years_span': (date_2 - date_1).days // 365
                }
            )

            queries.append(query)
            query_id += 1

        return queries

    def generate_causal_lineage_queries(self, n_queries: int = 10) -> List[BenchmarkQuery]:
        """Generate causal lineage queries (version history)."""
        queries = []
        articles = self._get_articles_with_versions(min_versions=3)

        # Prefer articles with complex history
        articles_sorted = sorted(articles, key=lambda a: a['version_count'], reverse=True)

        query_id = 0
        for article in articles_sorted[:n_queries]:
            component_id = article['component_id']
            versions = self._get_version_history(component_id)

            version_chain = [
                {
                    'version': v['version'],
                    'date': str(v['date_start']),
                    'amendment': v['amendment']
                }
                for v in versions
            ]

            difficulty = 'medium' if len(versions) <= 5 else 'hard'

            query = BenchmarkQuery(
                task='causal_lineage',
                query_id=f'lineage_{query_id:03d}',
                query=f"Show the complete version history of {self._get_component_name(component_id)} from 1988 to 2025",
                difficulty=difficulty,
                target_component=component_id,
                ground_truth={
                    'version_chain': version_chain,
                    'total_versions': len(versions)
                },
                metadata={
                    'complexity': len(versions)
                }
            )

            queries.append(query)
            query_id += 1

        return queries

    def generate_temporal_consistency_queries(self, n_queries: int = 10) -> List[BenchmarkQuery]:
        """Generate temporal consistency queries (negative tests)."""
        queries = []

        # Get articles that have NOT been amended (only 1 version)
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:Component)-[:HAS_VERSION]->(v:CTV)
                WHERE c.component_type = 'article'
                WITH c, count(v) AS version_count
                WHERE version_count = 1
                RETURN c.component_id AS component_id
                LIMIT $n
            """, n=n_queries)
            unamended_articles = [record['component_id'] for record in result]

        query_id = 0
        for component_id in unamended_articles:
            query = BenchmarkQuery(
                task='temporal_consistency',
                query_id=f'consist_{query_id:03d}',
                query=f"Has {self._get_component_name(component_id)} been amended since 1988?",
                difficulty='easy',
                target_component=component_id,
                ground_truth={
                    'amended': False,
                    'versions': 1,
                    'amendments': []
                }
            )

            queries.append(query)
            query_id += 1

        return queries

    def generate_hierarchical_impact_queries(self, n_queries: int = 15) -> List[BenchmarkQuery]:
        """Generate hierarchical impact analysis queries."""
        queries = []

        # Get titles with amended articles
        with self.driver.session() as session:
            result = session.run("""
                MATCH (title:Component)-[:HAS_CHILD*]->(art:Component)
                WHERE title.component_type = 'title'
                  AND art.component_type = 'article'
                  AND exists((art)-[:HAS_VERSION]->(:CTV)<-[:RESULTED_IN]-(:Action))
                WITH title, collect(DISTINCT art.component_id) AS affected_articles
                WHERE size(affected_articles) > 0
                RETURN title.component_id AS title_id,
                       affected_articles
                LIMIT $n
            """, n=n_queries)

            titles = [dict(record) for record in result]

        query_id = 0
        for title_data in titles:
            title_id = title_data['title_id']
            affected_articles = title_data['affected_articles']

            # Get title name
            title_num = title_id.split('_')[1]
            title_name = f"Title {title_num}"

            difficulty = 'medium' if len(affected_articles) <= 3 else 'hard'

            query = BenchmarkQuery(
                task='hierarchical_impact',
                query_id=f'hier_{query_id:03d}',
                query=f"Which articles in {title_name} have been amended since 2000?",
                difficulty=difficulty,
                target_component=title_id,
                date_range=['2000-01-01', '2025-01-01'],
                ground_truth={
                    'affected_articles': affected_articles,
                    'total_changes': len(affected_articles)
                },
                metadata={
                    'scope': 'title',
                    'requires_traversal': True
                }
            )

            queries.append(query)
            query_id += 1

        return queries

    def generate_full_benchmark(self) -> Dict:
        """Generate complete TLR-Bench dataset."""
        print("Generating TLR-Bench v1.0...")
        print("="*70)

        all_queries = []

        # Task 1: Point-in-Time (30 queries)
        print("\n📍 Generating Point-in-Time queries...")
        pit_queries = self.generate_point_in_time_queries(30)
        all_queries.extend(pit_queries)
        print(f"   Generated {len(pit_queries)} queries")

        # Task 2: Amendment Attribution (20 queries)
        print("\n🔍 Generating Amendment Attribution queries...")
        amend_queries = self.generate_amendment_attribution_queries(20)
        all_queries.extend(amend_queries)
        print(f"   Generated {len(amend_queries)} queries")

        # Task 3: Temporal Difference (15 queries)
        print("\n📊 Generating Temporal Difference queries...")
        diff_queries = self.generate_temporal_difference_queries(15)
        all_queries.extend(diff_queries)
        print(f"   Generated {len(diff_queries)} queries")

        # Task 4: Causal Lineage (10 queries)
        print("\n🔗 Generating Causal Lineage queries...")
        lineage_queries = self.generate_causal_lineage_queries(10)
        all_queries.extend(lineage_queries)
        print(f"   Generated {len(lineage_queries)} queries")

        # Task 5: Temporal Consistency (10 queries)
        print("\n✓ Generating Temporal Consistency queries...")
        consist_queries = self.generate_temporal_consistency_queries(10)
        all_queries.extend(consist_queries)
        print(f"   Generated {len(consist_queries)} queries")

        # Task 6: Hierarchical Impact (15 queries)
        print("\n🌳 Generating Hierarchical Impact queries...")
        hier_queries = self.generate_hierarchical_impact_queries(15)
        all_queries.extend(hier_queries)
        print(f"   Generated {len(hier_queries)} queries")

        print("\n" + "="*70)
        print(f"✅ Total queries generated: {len(all_queries)}")

        # Create benchmark dataset
        benchmark = {
            'metadata': {
                'name': 'TLR-Bench',
                'version': '1.0',
                'created': str(date.today()),
                'description': 'Temporal Legal Reasoning Benchmark for Brazilian Federal Constitution',
                'total_queries': len(all_queries),
                'data_source': 'Brazilian Federal Constitution (1988-2025)',
                'amendments_processed': 137,
                'components': 4195,
                'temporal_versions': 6284
            },
            'task_distribution': {
                'point_in_time': len([q for q in all_queries if q.task == 'point_in_time']),
                'amendment_attribution': len([q for q in all_queries if q.task == 'amendment_attribution']),
                'temporal_difference': len([q for q in all_queries if q.task == 'temporal_difference']),
                'causal_lineage': len([q for q in all_queries if q.task == 'causal_lineage']),
                'temporal_consistency': len([q for q in all_queries if q.task == 'temporal_consistency']),
                'hierarchical_impact': len([q for q in all_queries if q.task == 'hierarchical_impact'])
            },
            'difficulty_distribution': {
                'easy': len([q for q in all_queries if q.difficulty == 'easy']),
                'medium': len([q for q in all_queries if q.difficulty == 'medium']),
                'hard': len([q for q in all_queries if q.difficulty == 'hard'])
            },
            'queries': [asdict(q) for q in all_queries]
        }

        return benchmark


def main():
    """Generate TLR-Bench dataset."""
    generator = BenchmarkGenerator()

    try:
        benchmark = generator.generate_full_benchmark()

        # Save to file
        output_path = Path(__file__).parent.parent / "data" / "benchmark" / "tlr_bench_v1.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(benchmark, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Benchmark saved to: {output_path}")
        print("\n📊 Distribution:")
        print(f"   By Task: {benchmark['task_distribution']}")
        print(f"   By Difficulty: {benchmark['difficulty_distribution']}")

    finally:
        generator.close()


if __name__ == "__main__":
    main()
