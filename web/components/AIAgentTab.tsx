"use client";

import { useState } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Loader2, Activity } from "lucide-react";

interface AIAgentTabProps {
  loading: Record<string, boolean>;
  results: Record<string, any>;
  callApi: (key: string, path: string, method?: string, body?: any) => Promise<any>;
}

export function AIAgentTab({ loading, results, callApi }: AIAgentTabProps) {
  const [agentForm, setAgentForm] = useState({
    code: "005930",
    name: "",
    market: "J",
    ai_persona: "swing_short",
    anchor_ma: "20",
    target_mas: "5,10",
    threshold: "1.5",
  });

  const handleRunAnalysis = () => {
    const targetMasArray = agentForm.target_mas
      .split(",")
      .map((m) => parseInt(m.trim()))
      .filter((m) => !isNaN(m));

    callApi("agent_analyze", "/api/agent/analyze/auto", "POST", {
      stock_code: agentForm.code,
      stock_name: agentForm.name || undefined,
      market: agentForm.market,
      ai_persona: agentForm.ai_persona,
      anchor_ma: parseInt(agentForm.anchor_ma),
      target_mas: targetMasArray,
      convergence_threshold: parseFloat(agentForm.threshold),
    });
  };

  const analysis = results["agent_analyze"];

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-4">
      {/* Service Health Card */}
      <Card className="md:col-span-1 h-fit">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Activity className="h-4 w-4 text-green-500" /> Service Health
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button
            variant="outline"
            className="w-full"
            onClick={() => callApi("agent_health", "/api/agent/health")}
            disabled={loading["agent_health"]}
          >
            {loading["agent_health"] && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Check Health
          </Button>
          {results["agent_health"] && (
            <div className="p-3 rounded-md bg-zinc-100 dark:bg-zinc-900 text-xs font-mono overflow-auto max-h-[200px] border">
              <pre>{JSON.stringify(results["agent_health"], null, 2)}</pre>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Auto Analysis Card */}
      <Card className="md:col-span-2">
        <CardHeader>
          <CardTitle className="text-lg">Auto Analysis</CardTitle>
          <CardDescription>
            Analyze a stock using AI personas with dynamic strategy parameters.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label htmlFor="agent_market">Market</Label>
              <Select
                value={agentForm.market}
                onValueChange={(v) => setAgentForm({ ...agentForm, market: v })}
              >
                <SelectTrigger id="agent_market">
                  <SelectValue placeholder="Select market" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="J">KOSPI (J)</SelectItem>
                  <SelectItem value="Q">KOSDAQ (Q)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="stock_code">Stock Code</Label>
              <Input
                id="stock_code"
                placeholder="e.g. 005930"
                value={agentForm.code}
                onChange={(e) =>
                  setAgentForm({ ...agentForm, code: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="stock_name">Stock Name (Optional)</Label>
              <Input
                id="stock_name"
                placeholder="e.g. 삼성전자"
                value={agentForm.name}
                onChange={(e) =>
                  setAgentForm({ ...agentForm, name: e.target.value })
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 border-t pt-4">
            <div className="space-y-2">
              <Label htmlFor="ai_persona">AI Persona</Label>
              <Select
                value={agentForm.ai_persona}
                onValueChange={(v) =>
                  setAgentForm({ ...agentForm, ai_persona: v })
                }
              >
                <SelectTrigger id="ai_persona">
                  <SelectValue placeholder="Select persona" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="swing_short">Conservative Swing</SelectItem>
                  <SelectItem value="day_trade">Aggressive Day Trade</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="agent_anchor_ma">Anchor MA</Label>
              <Input
                id="agent_anchor_ma"
                type="number"
                value={agentForm.anchor_ma}
                onChange={(e) =>
                  setAgentForm({ ...agentForm, anchor_ma: e.target.value })
                }
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pb-2">
            <div className="space-y-2">
              <Label htmlFor="agent_target_mas">Target MAs (comma separated)</Label>
              <Input
                id="agent_target_mas"
                placeholder="e.g. 5,10,20"
                value={agentForm.target_mas}
                onChange={(e) =>
                  setAgentForm({ ...agentForm, target_mas: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="agent_threshold">Threshold (%)</Label>
              <Input
                id="agent_threshold"
                type="number"
                step="0.1"
                value={agentForm.threshold}
                onChange={(e) =>
                  setAgentForm({ ...agentForm, threshold: e.target.value })
                }
              />
            </div>
          </div>

          <Button
            className="w-full"
            onClick={handleRunAnalysis}
            disabled={loading["agent_analyze"]}
          >
            {loading["agent_analyze"] && (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            )}
            Run AI Analysis
          </Button>

          {analysis && (
            <div className="mt-4 p-4 rounded-lg border bg-zinc-50 dark:bg-zinc-950">
              <div className="flex justify-between items-center mb-4">
                <h4 className="font-semibold">Analysis Result: {analysis.stock_name || analysis.stock_code}</h4>
                <Badge variant="outline" className="font-mono">{analysis.trade_date}</Badge>
              </div>
              
              <div className="grid grid-cols-2 gap-4 text-sm mb-6">
                <div className="flex flex-col gap-1">
                  <span className="text-muted-foreground text-xs uppercase font-bold">
                    Final Position
                  </span>
                  <Badge
                    className={
                      analysis.final_position === "BUY"
                        ? "bg-red-500"
                        : analysis.final_position === "SELL"
                        ? "bg-blue-500"
                        : "bg-zinc-500"
                    }
                  >
                    {analysis.final_position || "UNKNOWN"}
                  </Badge>
                </div>
                <div className="flex flex-col gap-1">
                  <span className="text-muted-foreground text-xs uppercase font-bold">
                    Confidence
                  </span>
                  <span className="text-lg font-mono">
                    {(analysis.final_confidence * 10).toFixed(0)}%
                  </span>
                </div>
              </div>

              {analysis.warning_message && (
                <div className="mb-6 p-3 rounded bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900 text-amber-800 dark:text-amber-200 text-xs">
                  {analysis.warning_message}
                </div>
              )}

              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2 p-3 rounded border bg-white dark:bg-zinc-900">
                    <h5 className="text-sm font-bold flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-blue-500"></span>
                      Conservative Agent
                    </h5>
                    <div className="text-xs space-y-2">
                      <p className="font-medium text-zinc-500">
                        Position:{" "}
                        <Badge variant="outline" className="h-4 text-[10px]">
                          {analysis.conservative_agent?.position}
                        </Badge> (Conf: {analysis.conservative_agent?.confidence}/10)
                      </p>
                      <p className="leading-relaxed">
                        {analysis.conservative_agent?.reasoning?.chart_basis}
                      </p>
                    </div>
                  </div>
                  <div className="space-y-2 p-3 rounded border bg-white dark:bg-zinc-900">
                    <h5 className="text-sm font-bold flex items-center gap-2">
                      <span className="h-2 w-2 rounded-full bg-red-500"></span>
                      Aggressive Agent
                    </h5>
                    <div className="text-xs space-y-2">
                      <p className="font-medium text-zinc-500">
                        Position:{" "}
                        <Badge variant="outline" className="h-4 text-[10px]">
                          {analysis.aggressive_agent?.position}
                        </Badge> (Conf: {analysis.aggressive_agent?.confidence}/10)
                      </p>
                      <p className="leading-relaxed">
                        {analysis.aggressive_agent?.reasoning?.chart_basis}
                      </p>
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <h5 className="text-sm font-bold">Key Signals</h5>
                    <div className="flex flex-wrap gap-2">
                      {analysis.aggregated_signals?.map((s: string, i: number) => (
                        <Badge key={i} variant="secondary" className="text-[10px] py-0">
                          {s}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-2">
                    <h5 className="text-sm font-bold">Risk Factors</h5>
                    <div className="flex flex-wrap gap-2">
                      {analysis.aggregated_risks?.map((s: string, i: number) => (
                        <Badge key={i} variant="destructive" className="text-[10px] py-0 bg-transparent text-destructive border-destructive">
                          {s}
                        </Badge>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              <div className="mt-6 p-3 rounded bg-zinc-100 dark:bg-zinc-900 border text-[10px] overflow-auto max-h-[200px] font-mono">
                <pre>{JSON.stringify(analysis, null, 2)}</pre>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
