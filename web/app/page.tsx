"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Cpu, Zap, TrendingUp, Search } from "lucide-react";

// Refactored Components
import { AIAgentTab } from "@/components/AIAgentTab";
import { StrategyTab } from "@/components/StrategyTab";
import { RankingTab } from "@/components/RankingTab";
import { NewsTab } from "@/components/NewsTab";

export default function ApiTesterPage() {
  const [baseUrl, setBaseUrl] = useState("https://168.107.30.239.nip.io");
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<Record<string, any>>({});
  const [selectedStock, setSelectedStock] = useState<{
    code: string;
    name: string;
    market: string;
  } | null>(null);

  // Form states (kept here if they need to be shared, though most are now local to tabs)
  const [strategyForm, setStrategyForm] = useState({
    market: "Q",
    ma: "20",
    targetMas: "5,10",
    threshold: "1.5",
  });

  const callApi = async (
    key: string,
    path: string,
    method = "GET",
    body?: any
  ) => {
    setLoading((prev) => ({ ...prev, [key]: true }));
    try {
      const options: RequestInit = {
        method,
        headers: { "Content-Type": "application/json" },
      };
      if (body) options.body = JSON.stringify(body);

      const response = await fetch(`${baseUrl}${path}`, options);
      const data = await response.json();
      setResults((prev) => ({ ...prev, [key]: data }));
      return data;
    } catch (error) {
      console.error(`Error calling ${path}:`, error);
      setResults((prev) => ({ ...prev, [key]: { error: String(error) } }));
    } finally {
      setLoading((prev) => ({ ...prev, [key]: false }));
    }
  };

  const handleStockClick = async (
    code: string,
    name: string,
    market: string
  ) => {
    setSelectedStock({ code, name, market });
    await callApi(
      "stock_chart",
      `/api/stock/chart/${code}?market=${market}&count=120`
    );
  };

  const getMaPeriods = () => {
    const anchor = parseInt(strategyForm.ma);
    const targets = strategyForm.targetMas
      .split(",")
      .map((m) => parseInt(m.trim()))
      .filter((m) => !isNaN(m));
    return [anchor, ...targets].sort((a, b) => a - b);
  };

  return (
    <div className="container mx-auto py-10 px-4 max-w-6xl">
      <div className="flex flex-col gap-8">
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b pb-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">
              Trading API Tester
            </h1>
            <p className="text-muted-foreground">
              Test and monitor your trading backend endpoints.
            </p>
          </div>
          <div className="flex items-center gap-2 max-w-sm w-full">
            <Label htmlFor="baseUrl" className="whitespace-nowrap font-medium">
              Base URL
            </Label>
            <Input
              id="baseUrl"
              placeholder="API Base URL"
              value={baseUrl}
              onChange={(e) => setBaseUrl(e.target.value)}
              className="font-mono text-sm"
            />
          </div>
        </header>

        <Tabs defaultValue="agent" className="w-full">
          <TabsList className="grid w-full grid-cols-4 lg:w-[600px]">
            <TabsTrigger value="agent" className="flex items-center gap-2">
              <Cpu className="h-4 w-4" /> AI Agent
            </TabsTrigger>
            <TabsTrigger value="strategy" className="flex items-center gap-2">
              <Zap className="h-4 w-4" /> Strategy
            </TabsTrigger>
            <TabsTrigger value="ranking" className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4" /> Ranking
            </TabsTrigger>
            <TabsTrigger value="news" className="flex items-center gap-2">
              <Search className="h-4 w-4" /> News
            </TabsTrigger>
          </TabsList>

          <TabsContent value="agent">
            <AIAgentTab loading={loading} results={results} callApi={callApi} />
          </TabsContent>

          <TabsContent value="strategy">
            <StrategyTab
              strategyForm={strategyForm}
              setStrategyForm={setStrategyForm}
              loading={loading}
              results={results}
              callApi={callApi}
              selectedStock={selectedStock}
              setSelectedStock={setSelectedStock}
              handleStockClick={handleStockClick}
              getMaPeriods={getMaPeriods}
            />
          </TabsContent>

          <TabsContent value="ranking">
            <RankingTab loading={loading} results={results} callApi={callApi} />
          </TabsContent>

          <TabsContent value="news">
            <NewsTab loading={loading} results={results} callApi={callApi} />
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
