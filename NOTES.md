# Engineering notes

These notes explain the choices behind the fuel route planner: what I picked, what I turned down and why, and what I'd change with more time. The README covers how to run it.

## The problem as I read it

Given two places in the US, find the driving route, work out where to buy fuel so the trip costs as little as possible, and say how much it costs. The truck goes 500 miles on a full tank at 10 mpg. Prices come from the CSV we were given. The brief also asks for two things that shaped most of my decisions: the API should be fast, and it should call the outside map service as little as possible, once if it can.

## Getting coordinates without a geocoding API

The CSV has names, addresses and cities, but no coordinates. So before I could do anything with a route, every station needed a position on the map.

The obvious move was to look each one up with a free geocoder like Nominatim. I didn't, for three reasons. The file has about 8,000 rows. Nominatim allows one request a second, so a full load takes over two hours. And its usage policy discourages bulk jobs like this. On top of that, most addresses look like "I-44, EXIT 283 & US-69", which geocoders handle badly.

Instead I used the US Census gazetteer files, which list every US city, town and named place with a centre point. They're small (about 2.7 MB zipped), free, and I've checked them into `data/`. Each station gets the coordinates of its city. The same lookup handles the user's input, so "Chicago, IL" never goes to an outside service either.

A few details from cleaning the data:

- The CSV has 8,151 rows but only 6,738 distinct stations. Some appear twice, sometimes with different prices. I keep the lowest price for each one.
- About 600 rows are in Canada. The task is US only, so I drop them.
- Census names don't match the CSV exactly. The gazetteer says "Dallas city" and "Augusta-Richmond County consolidated government (balance)". I strip those suffixes and treat "Saint", "St." and "St" as the same.
- After all that, 6,423 of 6,626 US stations match. The other 203 are in very small unincorporated places the Census doesn't list. I could fill those in with a one-off Nominatim pass, but I left them out to keep loading simple and offline.

The cost of this approach is precision. A station is placed at its town's centre, not at the exact exit. I make up for that by accepting stations up to 10 miles from the route. On interstates that's a fair trade, since truck stops cluster around the towns they're named after.

## Routing

I used the public OSRM server. It's free, needs no API key, and one request returns the full road geometry plus distance and time. That one request is the only outside call in the whole flow.

Results are cached by start and finish coordinates. Asking for the same trip again, or opening its map page, doesn't call OSRM again.

The public OSRM server is a demo with no uptime promise. The base URL is a setting (`OSRM_BASE_URL`), so pointing at a self-hosted OSRM, or a paid provider behind the same small client, is a config change. If OSRM is down, the API returns a 502 instead of a vague 500.

## Finding the stations along the route

The route comes back with around 35,000 points for a coast-to-coast trip. I thin it to one point every half mile, which is plenty for this job and keeps everything after it fast.

Then three passes, from cheap to exact:

1. A database query for stations inside the route's bounding box.
2. A grid check. I mark the grid squares the route passes through and drop any station that isn't in or next to one of them. This throws away most of the country on a diagonal trip and costs almost nothing.
3. For what's left, the exact distance from each station to the nearest point on the route, done with numpy. Anything within 10 miles stays, and I record how far along the route it sits ("mile 393.9").

This takes about 100 ms for New York to Los Angeles. The rest of a first-time request is waiting on OSRM, usually 1 to 1.5 seconds. A cached repeat comes back in about 10 ms.

## Choosing where to stop

This is the part I went back and forth on.

My first version used the textbook approach: at each station, if somewhere cheaper is within reach, buy just enough to get there; otherwise fill up. It finds the true cheapest plan, and it gave New York to Los Angeles for $852.50. It also gave 18 stops, including one for 0.17 gallons to save about a cent. Nobody drives like that, and a reviewer looking at the output would rightly wonder what was going on.

So I changed it to a small dynamic programming solution that works backwards from the destination. At each stop the truck buys exactly enough fuel for the next leg, and each stop carries a $5 penalty that stands in for the time and hassle of pulling off the road. A stop only makes the plan if it saves more than $5. The same trip now has 7 stops and costs $864.91. That's $12 more than the theoretical minimum, for 11 fewer stops. I think that's the answer a real driver or dispatcher would want. The $5 is a setting if someone disagrees.

One bug worth mentioning: in my first version of the DP, if the destination was already in range, the code jumped straight to it and never checked whether a cheaper station on the way was worth stopping at. A unit test with two nearby stations caught it.

### Assumptions

- **The tank starts empty.** The first stop is the first station on the route, or any station in the first 10 miles. The fuel used to get there is charged at that station's price. I picked this so the total is the cost of fuel for the whole trip, and total gallons always equals distance divided by 10. The other option, starting full, gives $0 for any trip under 500 miles, which didn't seem like what the question was after.
- **Detours aren't counted.** If a station is 4 miles off the highway, those miles don't show up in the total.
- **Contiguous US only.** The price data doesn't cover Alaska or Hawaii, so points outside the lower 48 get a clear 400 error.

## How the code is organised

```
fuel/
  domain/          plain Python, no Django imports
  application/     the one use case: plan a trip
  infrastructure/  OSRM client, database queries, file readers
  api/             DRF serializers and views
```

The rule is that the code that does the actual thinking (route matching, choosing stops) knows nothing about Django, HTTP or OSRM. It takes lists of plain objects and returns plain objects. That made it easy to test with made-up numbers, and it means swapping the routing provider touches one file.

I tried not to go further than that. There are no abstract base classes or repository interfaces. The planner just takes two functions, one to get a route and one to find stations, and tests pass in fakes. There's one Django app and two models.

## Testing

18 tests, all passing:

- **Optimizer**: single stop, cheaper station ahead, picking the cheapest in range, total gallons always adding up, the stop penalty working, gaps longer than 500 miles being reported.
- **Route matching**: a nearby station gets the right mile marker, and a far one is dropped.
- **API**: the full request with OSRM mocked out, errors for bad input, a 502 when routing fails, and a check that the JSON endpoint and the map page share one routing call.

I also ran real trips against the live OSRM server (New York to LA, Chicago to Denver, Seattle to Miami, Dallas to Austin) and checked the map in a browser.

## What I'd do next

Roughly in order of value:

1. **Exact station locations.** One Nominatim pass over the addresses, run once and saved, would place stations at the right exit instead of the town centre. Then the corridor could shrink from 10 miles to 2 or 3.
2. **A shared cache.** The cache now lives in each server process's memory. With more than one worker, they should share Redis.
3. **Self-hosted routing.** For anything beyond a demo I wouldn't rely on the public OSRM server.
4. **Count detours.** Add the off-route distance to a stop's cost so a cheap station 9 miles away doesn't beat a slightly pricier one right at the exit.
5. **Street addresses as input.** Only "City, ST" and coordinates work today. Supporting full addresses would mean adding a geocoding call.
