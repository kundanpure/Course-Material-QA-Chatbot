"""
Learning Progress Service - Track student learning journey
Innovation: Analytics on what students have learned and knowledge gaps
"""
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from collections import Counter

from db.conversation_models import ConversationMessage, ConversationSession
from db.models import QueryLog
from core.logging import logger


class LearningProgressService:
    """
    Tracks learning progress and identifies knowledge gaps
    
    Features:
    - Topic coverage tracking
    - Knowledge gap identification
    - Study streak tracking
    - Performance analytics
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_learning_dashboard(
        self,
        user_id: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """
        Get comprehensive learning progress dashboard
        """
        
        # Get all user's conversations
        sessions_result = await self.session.execute(
            select(ConversationSession).where(
                and_(
                    ConversationSession.user_id == user_id,
                    ConversationSession.tenant_id == tenant_id
                )
            )
        )
        sessions = sessions_result.scalars().all()
        
        # Get all query logs
        logs_result = await self.session.execute(
            select(QueryLog).where(
                and_(
                    QueryLog.user_id == user_id,
                    QueryLog.tenant_id == tenant_id
                )
            ).order_by(desc(QueryLog.created_at)).limit(100)
        )
        logs = logs_result.scalars().all()
        
        # Calculate statistics
        total_questions = len(logs)
        total_conversations = len(sessions)
        
        # Topics discussed (from query types)
        topics = Counter([log.query_type for log in logs if log.query_type])
        
        # Study streak
        streak = await self._calculate_study_streak(user_id, tenant_id)
        
        # Average confidence
        avg_confidence = sum(log.confidence or 0 for log in logs) / max(1, total_questions)
        
        # Total time spent
        total_time_minutes = sum(log.total_time_ms or 0 for log in logs) / 60000
        
        # Recent activity
        if logs:
            last_active = logs[0].created_at
            days_since_start = (datetime.utcnow() - logs[-1].created_at).days
        else:
            last_active = None
            days_since_start = 0
        
        return {
            "total_questions_asked": total_questions,
            "total_conversations": total_conversations,
            "topics_discussed": dict(topics.most_common(10)),
            "study_streak_days": streak,
            "average_confidence": round(avg_confidence, 2),
            "total_study_time_minutes": round(total_time_minutes, 1),
            "last_active": last_active.isoformat() if last_active else None,
            "days_since_start": days_since_start,
            "cache_hit_rate": sum(1 for log in logs if log.was_cached) / max(1, total_questions)
        }
    
    async def _calculate_study_streak(
        self,
        user_id: str,
        tenant_id: str
    ) -> int:
        """Calculate consecutive days of study"""
        
        result = await self.session.execute(
            select(func.date(QueryLog.created_at).label('study_date')).where(
                and_(
                    QueryLog.user_id == user_id,
                    QueryLog.tenant_id == tenant_id
                )
            ).group_by(func.date(QueryLog.created_at)).order_by(desc('study_date'))
        )
        
        study_dates = [row[0] for row in result]
        
        if not study_dates:
            return 0
        
        # Calculate streak
        streak = 1
        for i in range(len(study_dates) - 1):
            diff = (study_dates[i] - study_dates[i+1]).days
            if diff == 1:
                streak += 1
            else:
                break
        
        return streak
    
    async def identify_knowledge_gaps(
        self,
        user_id: str,
        tenant_id: str,
        curriculum: List[str]
    ) -> Dict[str, Any]:
        """
        Identify knowledge gaps based on curriculum
        
        curriculum: List of topics that should be covered
        """
        
        # Get all topics discussed
        logs_result = await self.session.execute(
            select(QueryLog).where(
                and_(
                    QueryLog.user_id == user_id,
                    QueryLog.tenant_id == tenant_id
                )
            )
        )
        logs = logs_result.scalars().all()
        
        # Extract topics from queries (simplified - in production, use NLP)
        discussed_topics = set()
        for log in logs:
            # Simple keyword matching (upgrade to NER in production)
            query_lower = log.query.lower()
            for topic in curriculum:
                if topic.lower() in query_lower:
                    discussed_topics.add(topic)
        
        # Find gaps
        missing_topics = set(curriculum) - discussed_topics
        coverage_percentage = len(discussed_topics) / max(1, len(curriculum)) * 100
        
        # Weak areas (low confidence topics)
        topic_confidence = {}
        for topic in discussed_topics:
            relevant_logs = [log for log in logs if topic.lower() in log.query.lower()]
            avg_conf = sum(log.confidence or 0 for log in relevant_logs) / max(1, len(relevant_logs))
            topic_confidence[topic] = round(avg_conf, 2)
        
        weak_topics = [topic for topic, conf in topic_confidence.items() if conf < 0.75]
        
        return {
            "coverage_percentage": round(coverage_percentage, 1),
            "topics_covered": list(discussed_topics),
            "topics_missing": list(missing_topics),
            "weak_areas": weak_topics,
            "topic_confidence_scores": topic_confidence,
            "suggested_next": list(missing_topics)[:3] if missing_topics else []
        }
    
    async def get_study_recommendations(
        self,
        user_id: str,
        tenant_id: str
    ) -> List[Dict[str, str]]:
        """
        Get personalized study recommendations
        """
        
        recommendations = []
        
        # Check study streak
        streak = await self._calculate_study_streak(user_id, tenant_id)
        if streak == 0:
            recommendations.append({
                "type": "engagement",
                "priority": "high",
                "message": "Start your learning journey today!",
                "action": "Ask a question to begin"
            })
        elif streak < 3:
            recommendations.append({
                "type": "consistency",
                "priority": "medium",
                "message": f"Great start! You're on a {streak}-day streak 🔥",
                "action": "Study today to keep it going"
            })
        
        # Check recent activity
        logs_result = await self.session.execute(
            select(QueryLog).where(
                and_(
                    QueryLog.user_id == user_id,
                    QueryLog.tenant_id == tenant_id
                )
            ).order_by(desc(QueryLog.created_at)).limit(1)
        )
        last_log = logs_result.scalar_one_or_none()
        
        if last_log:
            days_since_last = (datetime.utcnow() - last_log.created_at).days
            if days_since_last >= 3:
                recommendations.append({
                    "type": "reminder",
                    "priority": "high",
                    "message": f"You haven't studied in {days_since_last} days",
                    "action": "Review your previous topics"
                })
        
        # Suggest weak areas review
        logs_result = await self.session.execute(
            select(QueryLog).where(
                and_(
                    QueryLog.user_id == user_id,
                    QueryLog.tenant_id == tenant_id,
                    QueryLog.confidence < 0.75
                )
            ).limit(5)
        )
        weak_queries = logs_result.scalars().all()
        
        if weak_queries:
            recommendations.append({
                "type": "review",
                "priority": "medium",
                "message": f"You have {len(weak_queries)} topics with low confidence",
                "action": "Review these topics to strengthen understanding"
            })
        
        return recommendations
    
    async def get_performance_analytics(
        self,
        user_id: str,
        tenant_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get performance analytics over time
        """
        
        since_date = datetime.utcnow() - timedelta(days=days)
        
        result = await self.session.execute(
            select(QueryLog).where(
                and_(
                    QueryLog.user_id == user_id,
                    QueryLog.tenant_id == tenant_id,
                    QueryLog.created_at >= since_date
                )
            ).order_by(QueryLog.created_at)
        )
        logs = result.scalars().all()
        
        # Group by day
        daily_stats = {}
        for log in logs:
            date_key = log.created_at.date().isoformat()
            if date_key not in daily_stats:
                daily_stats[date_key] = {
                    "questions": 0,
                    "avg_confidence": [],
                    "total_time_ms": 0
                }
            
            daily_stats[date_key]["questions"] += 1
            if log.confidence:
                daily_stats[date_key]["avg_confidence"].append(log.confidence)
            daily_stats[date_key]["total_time_ms"] += log.total_time_ms or 0
        
        # Calculate averages
        for date, stats in daily_stats.items():
            stats["avg_confidence"] = sum(stats["avg_confidence"]) / max(1, len(stats["avg_confidence"]))
        
        return {
            "period_days": days,
            "total_questions": len(logs),
            "daily_breakdown": daily_stats,
            "trend": "improving" if len(logs) > 10 else "starting"
        }


# Dependency injection
async def get_learning_progress_service(session: AsyncSession) -> LearningProgressService:
    return LearningProgressService(session)
