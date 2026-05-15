"use client";

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
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Loader2 } from "lucide-react";
import { StockChart } from "@/components/StockChart";

interface StrategyTabProps {
  strategyForm: {
    market: string;
    ma: string;
    targetMas: string;
    threshold: string;
  };
  setStrategyForm: (form: any) => void;
  loading: Record<string, boolean>;
  results: Record<string, any>;
  callApi: (key: string, path: string, method?: string, body?: any) => Promise<any>;
  selectedStock: { code: string; name: string; market: string } | null;
  setSelectedStock: (stock: any) => void;
  handleStockClick: (code: string, name: string, market: string) => Promise<void>;
  getMaPeriods: () => number[];
}

export function StrategyTab({
  strategyForm,
  setStrategyForm,
  loading,
  results,
  callApi,
  selectedStock,
  setSelectedStock,
  handleStockClick,
  getMaPeriods,
}: StrategyTabProps) {
  return (
    <div className="pt-4 space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Breakout Strategy Scanner</CardTitle>
          <CardDescription>
            Scan markets for breakout and convergence patterns.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div className="space-y-2">
              <Label htmlFor="market">Market</Label>
              <Select
                value={strategyForm.market}
                onValueChange={(val) =>
                  setStrategyForm({ ...strategyForm, market: val })
                }
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
                onChange={(e) =>
                  setStrategyForm({ ...strategyForm, ma: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="target_mas">Target MAs</Label>
              <Input
                id="target_mas"
                placeholder="e.g. 5,10,60"
                value={strategyForm.targetMas}
                onChange={(e) =>
                  setStrategyForm({ ...strategyForm, targetMas: e.target.value })
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="convergence">Threshold (%)</Label>
              <Input
                id="convergence"
                type="number"
                step="0.1"
                value={strategyForm.threshold}
                onChange={(e) =>
                  setStrategyForm({ ...strategyForm, threshold: e.target.value })
                }
              />
            </div>
            <div className="space-y-2 flex items-end">
              <Button
                className="w-full"
                onClick={() => {
                  const targetMasParams = strategyForm.targetMas
                    .split(",")
                    .map((m) => `target_mas=${m.trim()}`)
                    .join("&");
                  callApi(
                    "strategy_breakout",
                    `/api/strategy/breakout?market=${strategyForm.market}&anchor_ma=${strategyForm.ma}&convergence_threshold=${strategyForm.threshold}&${targetMasParams}`
                  );
                }}
                disabled={loading["strategy_breakout"]}
              >
                {loading["strategy_breakout"] && (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                )}
                Scan Market
              </Button>
            </div>
          </div>

          {results["strategy_breakout"] && (
            <div className="mt-6 space-y-4">
              <div className="flex flex-wrap gap-4">
                <Badge variant="outline">
                  Total Scanned: {results["strategy_breakout"].summary?.total_scanned}
                </Badge>
                <Badge className="bg-red-500">
                  Strong: {results["strategy_breakout"].summary?.breakout_strong}
                </Badge>
                <Badge className="bg-orange-500">
                  Normal: {results["strategy_breakout"].summary?.breakout_normal}
                </Badge>
                <Badge className="bg-blue-500">
                  Ready: {results["strategy_breakout"].summary?.ready}
                </Badge>
              </div>

              <div className="rounded-md border overflow-hidden">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Code</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Price</TableHead>
                      <TableHead>Score</TableHead>
                      <TableHead>Category</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {results["strategy_breakout"].results?.length > 0 ? (
                      results["strategy_breakout"].results
                        .slice(0, 20)
                        .map((item: any, i: number) => (
                          <TableRow
                            key={i}
                            className="cursor-pointer hover:bg-zinc-50 dark:hover:bg-zinc-900"
                            onClick={() =>
                              handleStockClick(
                                item.code,
                                item.name,
                                strategyForm.market
                              )
                            }
                          >
                            <TableCell className="font-mono">{item.code}</TableCell>
                            <TableCell className="font-medium">
                              {item.name}
                            </TableCell>
                            <TableCell>
                              {item.close?.toLocaleString()}
                            </TableCell>
                            <TableCell className="font-mono text-xs">
                              {item.convergence_score?.toFixed(4)}
                            </TableCell>
                            <TableCell>
                              <Badge
                                variant={
                                  item.breakout_category === "NONE"
                                    ? "secondary"
                                    : "default"
                                }
                                className={
                                  item.breakout_category === "BREAKOUT_STRONG"
                                    ? "bg-red-500"
                                    : item.breakout_category === "BREAKOUT_NORMAL"
                                    ? "bg-orange-500"
                                    : item.breakout_category === "READY"
                                    ? "bg-blue-500"
                                    : ""
                                }
                              >
                                {item.breakout_category}
                              </Badge>
                            </TableCell>
                          </TableRow>
                        ))
                    ) : (
                      <TableRow>
                        <TableCell
                          colSpan={5}
                          className="text-center py-10 text-muted-foreground"
                        >
                          No results found.
                        </TableCell>
                      </TableRow>
                    )}
                  </TableBody>
                </Table>
              </div>

              {selectedStock && (
                <Card className="mt-6">
                  <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                    <div>
                      <CardTitle className="text-lg">
                        {selectedStock.name} ({selectedStock.code})
                      </CardTitle>
                      <CardDescription>
                        1-minute candlestick chart
                      </CardDescription>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setSelectedStock(null)}
                    >
                      Close
                    </Button>
                  </CardHeader>
                  <CardContent>
                    {loading["stock_chart"] ? (
                      <div className="h-[400px] flex items-center justify-center">
                        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                      </div>
                    ) : results["stock_chart"]?.data ? (
                      <StockChart
                        data={results["stock_chart"].data}
                        maPeriods={getMaPeriods()}
                      />
                    ) : (
                      <div className="h-[400px] flex items-center justify-center text-muted-foreground">
                        Failed to load chart data.
                      </div>
                    )}
                  </CardContent>
                </Card>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
