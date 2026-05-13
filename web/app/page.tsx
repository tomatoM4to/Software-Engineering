"use client";

import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Loader2, Search, Zap, TrendingUp, Cpu, Activity } from "lucide-react";

export default function ApiTesterPage() {
  const [baseUrl, setBaseUrl] = useState("https://168.107.30.239.nip.io");
  const [loading, setLoading] = useState<Record<string, boolean>>({});
  const [results, setResults] = useState<Record<string, any>>({});

  // Form states
  const [agentForm, setAgentForm] = useState({ code: "005930", name: "", mode: "full" });
  const [strategyForm, setStrategyForm] = useState({ market: "Q", ma: "20", targetMas: "5,10", threshold: "1.5" });
  const [newsQuery, setNewsQuery] = useState("삼성전자");

  const callApi = async (key: string, path: string, method = "GET", body?: any) => {
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
    } catch (error) {
      console.error(`Error calling ${path}:`, error);
      setResults((prev) => ({ ...prev, [key]: { error: String(error) } }));
    } finally {
      setLoading((prev) => ({ ...prev, [key]: false }));
    }
  };

  return (
    <div className="container mx-auto py-10 px-4 max-w-6xl">
      <div className="flex flex-col gap-8">
        <header className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b pb-6">
          <div>
            <h1 className="text-3xl font-bold tracking-tight">Trading API Tester</h1>
            <p className="text-muted-foreground">Test and monitor your trading backend endpoints.</p>
          </div>
          <div className="flex items-center gap-2 max-w-sm w-full">
            <Label htmlFor="baseUrl" className="whitespace-nowrap font-medium">Base URL</Label>
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

          {/* AI Agent Tab */}
          <TabsContent value="agent" className="space-y-4 pt-4">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <Card className="md:col-span-1">
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Activity className="h-4 w-4 text-green-500" /> Service Health
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <Button 
                    variant="outline" 
                    className="w-full"
                    onClick={() => callApi('agent_health', '/api/agent/health')}
                    disabled={loading['agent_health']}
                  >
                    {loading['agent_health'] && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Check Health
                  </Button>
                  {results['agent_health'] && (
                    <div className="p-3 rounded-md bg-zinc-100 dark:bg-zinc-900 text-xs font-mono overflow-auto max-h-[200px] border">
                      <pre>{JSON.stringify(results['agent_health'], null, 2)}</pre>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card className="md:col-span-2">
                <CardHeader>
                  <CardTitle className="text-lg">Auto Analysis</CardTitle>
                  <CardDescription>Analyze a stock using AI personas.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="stock_code">Stock Code</Label>
                      <Input 
                        id="stock_code" 
                        placeholder="e.g. 005930" 
                        value={agentForm.code} 
                        onChange={(e) => setAgentForm({...agentForm, code: e.target.value})}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="stock_name">Stock Name (Optional)</Label>
                      <Input 
                        id="stock_name" 
                        placeholder="e.g. 삼성전자" 
                        value={agentForm.name}
                        onChange={(e) => setAgentForm({...agentForm, name: e.target.value})}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="analysis_mode">Mode</Label>
                      <Select 
                        value={agentForm.mode} 
                        onValueChange={(val) => setAgentForm({...agentForm, mode: val})}
                      >
                        <SelectTrigger id="analysis_mode">
                          <SelectValue placeholder="Select mode" />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="full">Full (Conservative + Aggressive)</SelectItem>
                          <SelectItem value="fast">Fast (Single Persona)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2 flex items-end">
                      <Button 
                        className="w-full"
                        onClick={() => callApi('agent_analyze', '/api/agent/analyze/auto', 'POST', {
                          stock_code: agentForm.code,
                          stock_name: agentForm.name,
                          analysis_mode: agentForm.mode
                        })}
                        disabled={loading['agent_analyze']}
                      >
                        {loading['agent_analyze'] && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                        Run Analysis
                      </Button>
                    </div>
                  </div>

                  {results['agent_analyze'] && (
                    <div className="mt-4 p-4 rounded-lg border bg-zinc-50 dark:bg-zinc-950">
                      <h4 className="font-semibold mb-2">Analysis Result</h4>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div className="flex flex-col gap-1">
                          <span className="text-muted-foreground text-xs uppercase font-bold">Position</span>
                          <Badge className={
                            results['agent_analyze'].final_position === 'BUY' ? 'bg-red-500' : 
                            results['agent_analyze'].final_position === 'SELL' ? 'bg-blue-500' : 'bg-zinc-500'
                          }>
                            {results['agent_analyze'].final_position || 'UNKNOWN'}
                          </Badge>
                        </div>
                        <div className="flex flex-col gap-1">
                          <span className="text-muted-foreground text-xs uppercase font-bold">Confidence</span>
                          <span className="text-lg font-mono">{(results['agent_analyze'].final_confidence * 100).toFixed(1)}%</span>
                        </div>
                      </div>
                      <div className="mt-4 p-3 rounded bg-white dark:bg-black border text-xs overflow-auto max-h-[300px]">
                         <pre>{JSON.stringify(results['agent_analyze'], null, 2)}</pre>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>
          </TabsContent>

          {/* Strategy Tab */}
          <TabsContent value="strategy" className="pt-4">
            <Card>
              <CardHeader>
                <CardTitle>Breakout Strategy Scanner</CardTitle>
                <CardDescription>Scan markets for breakout and convergence patterns.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="market">Market</Label>
                    <Select 
                      value={strategyForm.market} 
                      onValueChange={(val) => setStrategyForm({...strategyForm, market: val})}
                    >
                      <SelectTrigger id="market">
                        <SelectValue placeholder="Select market" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="J">KOSPI (J)</SelectItem>
                        <SelectItem value="Q">KOSDAQ (Q)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="anchor_ma">Anchor MA</Label>
                    <Input 
                      id="anchor_ma" 
                      type="number" 
                      value={strategyForm.ma}
                      onChange={(e) => setStrategyForm({...strategyForm, ma: e.target.value})}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="target_mas">Target MAs (comma separated)</Label>
                    <Input 
                      id="target_mas" 
                      placeholder="e.g. 5,10,60" 
                      value={strategyForm.targetMas}
                      onChange={(e) => setStrategyForm({...strategyForm, targetMas: e.target.value})}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="convergence">Threshold (%)</Label>
                    <Input 
                      id="convergence" 
                      type="number" 
                      step="0.1" 
                      value={strategyForm.threshold}
                      onChange={(e) => setStrategyForm({...strategyForm, threshold: e.target.value})}
                    />
                  </div>
                  <div className="space-y-2 flex items-end">
                    <Button 
                      className="w-full"
                      onClick={() => {
                        const targetMasParams = strategyForm.targetMas.split(',').map(m => `target_mas=${m.trim()}`).join('&');
                        callApi('strategy_breakout', `/api/strategy/breakout?market=${strategyForm.market}&anchor_ma=${strategyForm.ma}&convergence_threshold=${strategyForm.threshold}&${targetMasParams}`);
                      }}
                      disabled={loading['strategy_breakout']}
                    >
                      {loading['strategy_breakout'] && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                      Scan Market
                    </Button>
                  </div>
                </div>

                {results['strategy_breakout'] && (
                  <div className="mt-6 space-y-4">
                    <div className="flex gap-4">
                      <Badge variant="outline">Total Scanned: {results['strategy_breakout'].summary?.total_scanned}</Badge>
                      <Badge className="bg-red-500">Strong: {results['strategy_breakout'].summary?.breakout_strong}</Badge>
                      <Badge className="bg-orange-500">Normal: {results['strategy_breakout'].summary?.breakout_normal}</Badge>
                      <Badge className="bg-blue-500">Ready: {results['strategy_breakout'].summary?.ready}</Badge>
                    </div>
                    
                    <div className="rounded-md border overflow-hidden">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Code</TableHead>
                            <TableHead>Name</TableHead>
                            <TableHead>Price</TableHead>
                            <TableHead>Change %</TableHead>
                            <TableHead>Category</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {results['strategy_breakout'].results?.length > 0 ? (
                            results['strategy_breakout'].results.slice(0, 10).map((item: any, i: number) => (
                              <TableRow key={i}>
                                <TableCell className="font-mono">{item.stock_code}</TableCell>
                                <TableCell className="font-medium">{item.stock_name}</TableCell>
                                <TableCell>{parseInt(item.current_price).toLocaleString()}</TableCell>
                                <TableCell className={parseFloat(item.change_rate) >= 0 ? 'text-red-500' : 'text-blue-500'}>
                                  {item.change_rate}%
                                </TableCell>
                                <TableCell>
                                  <Badge variant={item.breakout_category === 'NONE' ? 'secondary' : 'default'}>
                                    {item.breakout_category}
                                  </Badge>
                                </TableCell>
                              </TableRow>
                            ))
                          ) : (
                            <TableRow>
                              <TableCell colSpan={5} className="text-center py-10 text-muted-foreground">No results found.</TableCell>
                            </TableRow>
                          )}
                        </TableBody>
                      </Table>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* Ranking Tab */}
          <TabsContent value="ranking" className="pt-4">
            <Card>
              <CardHeader>
                <CardTitle>Volume Ranking</CardTitle>
                <CardDescription>Get top stocks by trading volume.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <Button 
                  onClick={() => callApi('ranking_volume', '/api/ranking/volume')}
                  disabled={loading['ranking_volume']}
                >
                  {loading['ranking_volume'] && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                  Fetch Volume Ranking
                </Button>

                {results['ranking_volume'] && (
                  <div className="rounded-md border overflow-hidden">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Rank</TableHead>
                          <TableHead>Code</TableHead>
                          <TableHead>Name</TableHead>
                          <TableHead>Price</TableHead>
                          <TableHead>Change %</TableHead>
                          <TableHead>Volume</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {Array.isArray(results['ranking_volume']) ? (
                          results['ranking_volume'].map((item: any, i: number) => (
                            <TableRow key={i}>
                              <TableCell>{item.data_rank}</TableCell>
                              <TableCell className="font-mono">{item.mkp_shrn_iscd}</TableCell>
                              <TableCell className="font-medium">{item.hts_kor_isnm}</TableCell>
                              <TableCell>{parseInt(item.stck_prpr).toLocaleString()}</TableCell>
                              <TableCell className={parseFloat(item.prdy_ctrt) >= 0 ? 'text-red-500' : 'text-blue-500'}>
                                {item.prdy_ctrt}%
                              </TableCell>
                              <TableCell>{parseInt(item.acml_tr_pbmn).toLocaleString()}</TableCell>
                            </TableRow>
                          ))
                        ) : (
                           <TableRow>
                              <TableCell colSpan={6} className="text-center py-10 text-red-500">Failed to load data.</TableCell>
                           </TableRow>
                        )}
                      </TableBody>
                    </Table>
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          {/* News Tab */}
          <TabsContent value="news" className="pt-4">
            <Card>
              <CardHeader>
                <CardTitle>News Search</CardTitle>
                <CardDescription>Search for news on Naver.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex gap-4">
                  <div className="flex-1">
                    <Input 
                      placeholder="Enter keywords..." 
                      value={newsQuery} 
                      onChange={(e) => setNewsQuery(e.target.value)}
                    />
                  </div>
                  <Button 
                    onClick={() => callApi('news_search', `/news/search?query=${encodeURIComponent(newsQuery)}`)}
                    disabled={loading['news_search']}
                  >
                    {loading['news_search'] && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                    Search
                  </Button>
                </div>

                {results['news_search'] && (
                  <div className="space-y-4">
                    {results['news_search'].items?.map((news: any, i: number) => (
                      <div key={i} className="p-4 rounded-lg border hover:bg-zinc-50 dark:hover:bg-zinc-950 transition-colors">
                        <h4 className="font-semibold text-blue-600 dark:text-blue-400" dangerouslySetInnerHTML={{ __html: news.title }}></h4>
                        <p className="text-sm text-muted-foreground mt-1" dangerouslySetInnerHTML={{ __html: news.description }}></p>
                        <div className="flex justify-between items-center mt-2">
                          <span className="text-xs text-muted-foreground">{new Date(news.pubDate).toLocaleString()}</span>
                          <a href={news.link} target="_blank" rel="noreferrer" className="text-xs font-medium hover:underline text-zinc-500">Link &rarr;</a>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </div>
  );
}
