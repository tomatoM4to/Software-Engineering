"use client";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Loader2 } from "lucide-react";
import { useState } from "react";

interface RankingTabProps {
  loading: Record<string, boolean>;
  results: Record<string, any>;
  callApi: (key: string, path: string, method?: string, body?: any) => Promise<any>;
}

export function RankingTab({ loading, results, callApi }: RankingTabProps) {
  const [market, setMarket] = useState("kospi");

  return (
    <div className="pt-4">
      <Card>
        <CardHeader>
          <CardTitle>Volume Ranking</CardTitle>
          <CardDescription>Get top stocks by trading volume.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4">
            <Select value={market} onValueChange={setMarket}>
              <SelectTrigger className="w-[180px]">
                <SelectValue placeholder="Select Market" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="kospi">KOSPI</SelectItem>
                <SelectItem value="kosdaq">KOSDAQ</SelectItem>
              </SelectContent>
            </Select>

            <Button
              onClick={() =>
                callApi("ranking_volume", `/api/ranking/volume?market=${market}`)
              }
              disabled={loading["ranking_volume"]}
            >
              {loading["ranking_volume"] && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Fetch Volume Ranking
            </Button>
          </div>

          {results["ranking_volume"] && (
            <div className="rounded-md border overflow-hidden">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Rank</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Price</TableHead>
                    <TableHead>Change %</TableHead>
                    <TableHead>Volume</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {Array.isArray(results["ranking_volume"]) ? (
                    results["ranking_volume"].map((item: any, i: number) => (
                      <TableRow key={i}>
                        <TableCell>{item.data_rank}</TableCell>
                        <TableCell className="font-medium">
                          {item.hts_kor_isnm}
                        </TableCell>
                        <TableCell>
                          {parseInt(item.stck_prpr).toLocaleString()}
                        </TableCell>
                        <TableCell
                          className={
                            parseFloat(item.prdy_ctrt) >= 0
                              ? "text-red-500"
                              : "text-blue-500"
                          }
                        >
                          {item.prdy_ctrt}%
                        </TableCell>
                        <TableCell>
                          {parseInt(item.acml_tr_pbmn).toLocaleString()}
                        </TableCell>
                      </TableRow>
                    ))
                  ) : (
                    <TableRow>
                      <TableCell
                        colSpan={5}
                        className="text-center py-10 text-red-500"
                      >
                        Failed to load data.
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
