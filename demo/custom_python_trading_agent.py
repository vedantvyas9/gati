"""
Custom Python Trading Agent with GATI SDK Integration
======================================================
A sophisticated trading analysis system using custom Python with GATI SDK decorators
for complete observability.

This demo showcases:
- Multi-agent trading system (analyst, risk manager, trader, portfolio manager)
- Real LLM calls for decision making
- Complex tool usage (market data, risk analysis, portfolio operations)
- Full GATI SDK integration with @track_agent and @track_tool decorators
- Real-world financial decision workflow

The system analyzes market conditions, assesses risks, executes trades,
and manages a portfolio with full observability through GATI.
"""

import os
import json
import time
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dotenv import load_dotenv
import random

# GATI SDK imports
from gati.observe import observe
from gati.decorators import track_agent, track_tool

# OpenAI import
from openai import OpenAI

# Load environment variables
load_dotenv()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize GATI observe
observe.init(
    backend_url="http://localhost:8000",
    buffer_size=100,
    flush_interval=5.0
)


# ===== Tool Functions (All tracked with GATI) =====

@track_tool(name="fetch_market_data")
def fetch_market_data(symbol: str, period: str = "1d") -> Dict[str, Any]:
    """
    Fetches market data for a given symbol.

    Args:
        symbol: Stock symbol (e.g., 'AAPL', 'GOOGL')
        period: Time period ('1d', '1w', '1m')

    Returns:
        Market data including price, volume, and trends
    """
    time.sleep(0.4)  # Simulate API call

    # Simulate realistic market data
    base_prices = {
        "AAPL": 178.50,
        "GOOGL": 141.80,
        "MSFT": 378.90,
        "AMZN": 151.20,
        "TSLA": 242.80
    }

    base_price = base_prices.get(symbol, 100.0)
    current_price = base_price * (1 + random.uniform(-0.05, 0.05))

    return {
        "symbol": symbol,
        "price": round(current_price, 2),
        "volume": random.randint(50000000, 100000000),
        "change_percent": round(random.uniform(-3, 3), 2),
        "day_high": round(current_price * 1.02, 2),
        "day_low": round(current_price * 0.98, 2),
        "52_week_high": round(base_price * 1.25, 2),
        "52_week_low": round(base_price * 0.75, 2),
        "market_cap": f"${random.randint(500, 3000)}B",
        "pe_ratio": round(random.uniform(15, 40), 2),
        "timestamp": datetime.now().isoformat()
    }


@track_tool(name="fetch_technical_indicators")
def fetch_technical_indicators(symbol: str) -> Dict[str, Any]:
    """
    Calculates technical indicators for a symbol.

    Args:
        symbol: Stock symbol

    Returns:
        Technical indicators (RSI, MACD, moving averages)
    """
    time.sleep(0.3)

    return {
        "symbol": symbol,
        "rsi": round(random.uniform(30, 70), 2),
        "macd": {
            "value": round(random.uniform(-2, 2), 2),
            "signal": round(random.uniform(-2, 2), 2),
            "histogram": round(random.uniform(-1, 1), 2)
        },
        "moving_averages": {
            "sma_20": round(random.uniform(170, 180), 2),
            "sma_50": round(random.uniform(165, 185), 2),
            "ema_12": round(random.uniform(172, 178), 2),
            "ema_26": round(random.uniform(170, 180), 2)
        },
        "bollinger_bands": {
            "upper": round(random.uniform(180, 185), 2),
            "middle": round(random.uniform(175, 180), 2),
            "lower": round(random.uniform(170, 175), 2)
        },
        "timestamp": datetime.now().isoformat()
    }


@track_tool(name="fetch_news_sentiment")
def fetch_news_sentiment(symbol: str) -> Dict[str, Any]:
    """
    Fetches recent news and sentiment analysis for a symbol.

    Args:
        symbol: Stock symbol

    Returns:
        News articles and sentiment scores
    """
    time.sleep(0.5)

    sentiments = ["positive", "neutral", "negative"]
    articles = [
        f"{symbol} shows strong quarterly earnings",
        f"Analysts upgrade {symbol} price target",
        f"{symbol} announces new product line",
        f"Market volatility affects {symbol} trading",
        f"{symbol} CEO discusses future strategy"
    ]

    return {
        "symbol": symbol,
        "overall_sentiment": random.choice(sentiments),
        "sentiment_score": round(random.uniform(-1, 1), 2),
        "articles": [
            {
                "headline": random.choice(articles),
                "sentiment": random.choice(sentiments),
                "published": (datetime.now() - timedelta(hours=random.randint(1, 24))).isoformat()
            }
            for _ in range(3)
        ],
        "timestamp": datetime.now().isoformat()
    }


@track_tool(name="calculate_risk_metrics")
def calculate_risk_metrics(symbol: str, position_size: float) -> Dict[str, Any]:
    """
    Calculates risk metrics for a potential trade.

    Args:
        symbol: Stock symbol
        position_size: Size of the position in dollars

    Returns:
        Risk metrics including VaR, beta, volatility
    """
    time.sleep(0.3)

    return {
        "symbol": symbol,
        "position_size": position_size,
        "value_at_risk_95": round(position_size * random.uniform(0.05, 0.15), 2),
        "beta": round(random.uniform(0.8, 1.5), 2),
        "volatility": round(random.uniform(0.15, 0.45), 2),
        "sharpe_ratio": round(random.uniform(0.5, 2.5), 2),
        "max_drawdown": round(random.uniform(0.10, 0.25), 2),
        "correlation_to_market": round(random.uniform(0.6, 0.95), 2),
        "risk_grade": random.choice(["A", "B", "C"]),
        "timestamp": datetime.now().isoformat()
    }


@track_tool(name="get_portfolio_status")
def get_portfolio_status() -> Dict[str, Any]:
    """
    Gets current portfolio status.

    Returns:
        Portfolio positions, cash, and performance metrics
    """
    time.sleep(0.2)

    return {
        "total_value": 100000.00,
        "cash": 45000.00,
        "invested": 55000.00,
        "positions": [
            {"symbol": "AAPL", "shares": 100, "avg_cost": 175.00, "current_value": 17850.00},
            {"symbol": "GOOGL", "shares": 150, "avg_cost": 138.00, "current_value": 21270.00},
            {"symbol": "MSFT", "shares": 50, "avg_cost": 370.00, "current_value": 18945.00}
        ],
        "day_gain": 1234.56,
        "day_gain_percent": 1.25,
        "total_gain": 5567.89,
        "total_gain_percent": 5.85,
        "timestamp": datetime.now().isoformat()
    }


@track_tool(name="execute_trade")
def execute_trade(symbol: str, action: str, quantity: int, price: float) -> Dict[str, Any]:
    """
    Executes a trade (buy/sell).

    Args:
        symbol: Stock symbol
        action: 'buy' or 'sell'
        quantity: Number of shares
        price: Execution price

    Returns:
        Trade confirmation
    """
    time.sleep(0.6)  # Simulate order execution

    order_id = f"ORD-{int(time.time())}-{random.randint(1000, 9999)}"

    return {
        "order_id": order_id,
        "symbol": symbol,
        "action": action,
        "quantity": quantity,
        "price": price,
        "total": round(quantity * price, 2),
        "status": "filled",
        "executed_at": datetime.now().isoformat(),
        "commission": round(quantity * price * 0.001, 2)  # 0.1% commission
    }


@track_tool(name="update_portfolio")
def update_portfolio(trade_details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updates portfolio after trade execution.

    Args:
        trade_details: Details of the executed trade

    Returns:
        Updated portfolio status
    """
    time.sleep(0.2)

    return {
        "updated": True,
        "trade_recorded": trade_details["order_id"],
        "new_position": {
            "symbol": trade_details["symbol"],
            "shares": trade_details["quantity"],
            "avg_cost": trade_details["price"]
        },
        "portfolio_value": 105000.00,  # Simulated new value
        "timestamp": datetime.now().isoformat()
    }


# ===== Agent Functions (All tracked with GATI) =====

@track_agent(name="market_analyst")
def market_analyst_agent(symbol: str) -> Dict[str, Any]:
    """
    Analyzes market conditions for a given symbol using multiple data sources.

    Args:
        symbol: Stock symbol to analyze

    Returns:
        Comprehensive market analysis with recommendation
    """
    print(f"\n[MARKET ANALYST] Analyzing {symbol}...")

    # Gather data using tracked tools
    market_data = fetch_market_data(symbol)
    technical_indicators = fetch_technical_indicators(symbol)
    news_sentiment = fetch_news_sentiment(symbol)

    # Use LLM to analyze the data
    analysis_prompt = f"""You are an expert market analyst. Analyze the following data for {symbol} and provide a recommendation.

Market Data:
{json.dumps(market_data, indent=2)}

Technical Indicators:
{json.dumps(technical_indicators, indent=2)}

News Sentiment:
{json.dumps(news_sentiment, indent=2)}

Provide your analysis in JSON format:
{{
  "recommendation": "buy|hold|sell",
  "confidence": 0.0-1.0,
  "reasoning": "brief explanation",
  "key_factors": ["factor1", "factor2", "factor3"],
  "price_target": price_in_dollars,
  "time_horizon": "short|medium|long"
}}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are an expert market analyst. Always respond with valid JSON."},
            {"role": "user", "content": analysis_prompt}
        ],
        temperature=0.7
    )

    try:
        analysis = json.loads(response.choices[0].message.content)
    except:
        # Fallback if JSON parsing fails
        analysis = {
            "recommendation": "hold",
            "confidence": 0.5,
            "reasoning": "Unable to parse LLM response",
            "key_factors": ["data analysis"],
            "price_target": market_data["price"],
            "time_horizon": "medium"
        }

    print(f"  Recommendation: {analysis['recommendation']} (confidence: {analysis['confidence']})")

    return {
        "symbol": symbol,
        "analysis": analysis,
        "data_sources": {
            "market_data": market_data,
            "technical_indicators": technical_indicators,
            "news_sentiment": news_sentiment
        }
    }


@track_agent(name="risk_manager")
def risk_manager_agent(symbol: str, proposed_action: str, proposed_quantity: int, current_price: float) -> Dict[str, Any]:
    """
    Assesses risk for a proposed trade.

    Args:
        symbol: Stock symbol
        proposed_action: 'buy' or 'sell'
        proposed_quantity: Number of shares
        current_price: Current stock price

    Returns:
        Risk assessment with approval decision
    """
    print(f"\n[RISK MANAGER] Assessing risk for {proposed_action} {proposed_quantity} shares of {symbol}...")

    position_size = proposed_quantity * current_price

    # Get risk metrics and portfolio status
    risk_metrics = calculate_risk_metrics(symbol, position_size)
    portfolio = get_portfolio_status()

    # Use LLM to make risk decision
    risk_prompt = f"""You are a risk management expert. Evaluate this proposed trade:

Action: {proposed_action.upper()}
Symbol: {symbol}
Quantity: {proposed_quantity} shares
Price: ${current_price}
Position Size: ${position_size}

Risk Metrics:
{json.dumps(risk_metrics, indent=2)}

Current Portfolio:
{json.dumps(portfolio, indent=2)}

Evaluate if this trade should be approved based on:
1. Position sizing (should not exceed 25% of portfolio)
2. Risk metrics (VaR, volatility, Sharpe ratio)
3. Portfolio diversification
4. Available cash

Respond in JSON format:
{{
  "approved": true|false,
  "risk_score": 0.0-1.0,
  "reasoning": "brief explanation",
  "concerns": ["concern1", "concern2"],
  "recommended_quantity": adjusted_quantity_if_needed
}}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a risk management expert. Always respond with valid JSON."},
            {"role": "user", "content": risk_prompt}
        ],
        temperature=0.3
    )

    try:
        risk_assessment = json.loads(response.choices[0].message.content)
    except:
        # Conservative fallback
        risk_assessment = {
            "approved": False,
            "risk_score": 0.8,
            "reasoning": "Unable to parse risk assessment",
            "concerns": ["parsing error"],
            "recommended_quantity": 0
        }

    print(f"  Approved: {risk_assessment['approved']} (risk score: {risk_assessment['risk_score']})")

    return {
        "symbol": symbol,
        "proposed_action": proposed_action,
        "proposed_quantity": proposed_quantity,
        "risk_assessment": risk_assessment,
        "risk_metrics": risk_metrics,
        "portfolio_status": portfolio
    }


@track_agent(name="trader")
def trader_agent(symbol: str, action: str, quantity: int, price: float) -> Dict[str, Any]:
    """
    Executes approved trades.

    Args:
        symbol: Stock symbol
        action: 'buy' or 'sell'
        quantity: Number of shares
        price: Execution price

    Returns:
        Trade execution result
    """
    print(f"\n[TRADER] Executing {action} order for {quantity} shares of {symbol} at ${price}...")

    # Execute the trade
    trade_result = execute_trade(symbol, action, quantity, price)

    print(f"  Order {trade_result['order_id']} {trade_result['status']}")
    print(f"  Total: ${trade_result['total']} (commission: ${trade_result['commission']})")

    return {
        "symbol": symbol,
        "trade_result": trade_result,
        "executed": True
    }


@track_agent(name="portfolio_manager")
def portfolio_manager_agent(trade_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updates portfolio and generates performance report.

    Args:
        trade_result: Result from trader agent

    Returns:
        Updated portfolio status and performance metrics
    """
    print(f"\n[PORTFOLIO MANAGER] Updating portfolio after trade...")

    # Update portfolio
    portfolio_update = update_portfolio(trade_result["trade_result"])

    # Get updated portfolio status
    updated_portfolio = get_portfolio_status()

    # Use LLM to generate performance summary
    summary_prompt = f"""You are a portfolio manager. Generate a brief performance summary:

Recent Trade:
{json.dumps(trade_result, indent=2)}

Updated Portfolio:
{json.dumps(updated_portfolio, indent=2)}

Provide a summary in JSON format:
{{
  "performance_summary": "brief summary",
  "portfolio_health": "excellent|good|fair|poor",
  "recommendations": ["recommendation1", "recommendation2"],
  "next_steps": ["step1", "step2"]
}}"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a portfolio manager. Always respond with valid JSON."},
            {"role": "user", "content": summary_prompt}
        ],
        temperature=0.5
    )

    try:
        summary = json.loads(response.choices[0].message.content)
    except:
        summary = {
            "performance_summary": "Portfolio updated successfully",
            "portfolio_health": "good",
            "recommendations": ["Continue monitoring"],
            "next_steps": ["Review performance"]
        }

    print(f"  Portfolio health: {summary['portfolio_health']}")

    return {
        "portfolio_update": portfolio_update,
        "current_portfolio": updated_portfolio,
        "summary": summary
    }


# ===== Main Trading Workflow (Tracked with GATI) =====

@track_agent(name="trading_system_orchestrator")
def trading_system_orchestrator(symbol: str, initial_quantity: int) -> Dict[str, Any]:
    """
    Orchestrates the entire trading workflow.

    Args:
        symbol: Stock symbol to trade
        initial_quantity: Initial desired quantity

    Returns:
        Complete workflow results
    """
    print("\n" + "="*60)
    print(f"TRADING SYSTEM - Processing {symbol}")
    print("="*60)

    workflow_results = {
        "symbol": symbol,
        "initial_quantity": initial_quantity,
        "stages": []
    }

    # Stage 1: Market Analysis
    print("\n[STAGE 1: MARKET ANALYSIS]")
    analysis_result = market_analyst_agent(symbol)
    workflow_results["stages"].append({
        "stage": "market_analysis",
        "result": analysis_result
    })

    recommendation = analysis_result["analysis"]["recommendation"]
    confidence = analysis_result["analysis"]["confidence"]
    current_price = analysis_result["data_sources"]["market_data"]["price"]

    # Only proceed if recommendation is to buy with sufficient confidence
    if recommendation != "buy" or confidence < 0.6:
        print(f"\n[DECISION] Not proceeding with trade. Recommendation: {recommendation}, Confidence: {confidence}")
        workflow_results["decision"] = "no_trade"
        workflow_results["reason"] = f"Recommendation was {recommendation} with {confidence} confidence"
        return workflow_results

    # Stage 2: Risk Management
    print("\n[STAGE 2: RISK MANAGEMENT]")
    risk_result = risk_manager_agent(symbol, "buy", initial_quantity, current_price)
    workflow_results["stages"].append({
        "stage": "risk_management",
        "result": risk_result
    })

    if not risk_result["risk_assessment"]["approved"]:
        print(f"\n[DECISION] Trade rejected by risk management")
        workflow_results["decision"] = "rejected"
        workflow_results["reason"] = risk_result["risk_assessment"]["reasoning"]
        return workflow_results

    # Use recommended quantity from risk manager
    approved_quantity = risk_result["risk_assessment"].get("recommended_quantity", initial_quantity)

    # Stage 3: Trade Execution
    print("\n[STAGE 3: TRADE EXECUTION]")
    trade_result = trader_agent(symbol, "buy", approved_quantity, current_price)
    workflow_results["stages"].append({
        "stage": "trade_execution",
        "result": trade_result
    })

    # Stage 4: Portfolio Management
    print("\n[STAGE 4: PORTFOLIO MANAGEMENT]")
    portfolio_result = portfolio_manager_agent(trade_result)
    workflow_results["stages"].append({
        "stage": "portfolio_management",
        "result": portfolio_result
    })

    workflow_results["decision"] = "trade_executed"
    workflow_results["final_status"] = portfolio_result["summary"]

    return workflow_results


# ===== Main Execution =====

def main():
    """Main execution function."""
    print("\n" + "="*60)
    print("CUSTOM PYTHON TRADING AGENT WITH GATI SDK")
    print("="*60)
    print("\nGATI observe initialized")
    print(f"Backend URL: http://localhost:8000")
    print("All agents and tools are being tracked!")

    # Trading parameters
    symbol = "AAPL"
    desired_quantity = 50

    try:
        # Run the trading system
        result = trading_system_orchestrator(symbol, desired_quantity)

        # Print final results
        print("\n" + "="*60)
        print("TRADING WORKFLOW RESULTS")
        print("="*60)
        print(f"\nSymbol: {result['symbol']}")
        print(f"Initial Quantity: {result['initial_quantity']}")
        print(f"Decision: {result['decision']}")

        if result['decision'] == 'trade_executed':
            print(f"\nFinal Status:")
            print(json.dumps(result['final_status'], indent=2))
        else:
            print(f"\nReason: {result.get('reason', 'N/A')}")

        print(f"\nStages Completed: {len(result['stages'])}")
        for stage in result['stages']:
            print(f"  - {stage['stage']}")

        print("\n" + "="*60)
        print("GATI OBSERVABILITY")
        print("="*60)
        print("All events have been tracked and sent to GATI backend")
        print("Check the dashboard at http://localhost:3000 to view:")
        print("  - Agent executions (market_analyst, risk_manager, trader, portfolio_manager)")
        print("  - Tool calls (fetch_market_data, calculate_risk_metrics, execute_trade, etc.)")
        print("  - Execution times and costs")
        print("  - Complete workflow trace")

        # Give buffer time to flush
        print("\nWaiting for buffer to flush...")
        time.sleep(6)

        print("\n\nWorkflow completed successfully!")

    except Exception as e:
        print(f"\nError during workflow execution: {str(e)}")
        raise
    finally:
        # Ensure buffer is flushed
        observe.flush()
        print("\nGATI buffer flushed")


if __name__ == "__main__":
    main()
