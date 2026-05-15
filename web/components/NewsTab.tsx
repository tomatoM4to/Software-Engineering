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
import { Loader2 } from "lucide-react";

interface NewsTabProps {
  loading: Record<string, boolean>;
  results: Record<string, any>;
  callApi: (key: string, path: string, method?: string, body?: any) => Promise<any>;
}

export function NewsTab({ loading, results, callApi }: NewsTabProps) {
  const [newsQuery, setNewsQuery] = useState("삼성전자");

  return (
    <div className="pt-4">
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
              onClick={() =>
                callApi(
                  "news_search",
                  `/news/search?query=${encodeURIComponent(newsQuery)}`
                )
              }
              disabled={loading["news_search"]}
            >
              {loading["news_search"] && (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              )}
              Search
            </Button>
          </div>

          {results["news_search"] && (
            <div className="space-y-4">
              {results["news_search"].items?.map((news: any, i: number) => (
                <div
                  key={i}
                  className="p-4 rounded-lg border hover:bg-zinc-50 dark:hover:bg-zinc-950 transition-colors"
                >
                  <h4
                    className="font-semibold text-blue-600 dark:text-blue-400"
                    dangerouslySetInnerHTML={{ __html: news.title }}
                  ></h4>
                  <p
                    className="text-sm text-muted-foreground mt-1"
                    dangerouslySetInnerHTML={{ __html: news.description }}
                  ></p>
                  <div className="flex justify-between items-center mt-2">
                    <span className="text-xs text-muted-foreground">
                      {new Date(news.pubDate).toLocaleString()}
                    </span>
                    <a
                      href={news.link}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs font-medium hover:underline text-zinc-500"
                    >
                      Link &rarr;
                    </a>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
