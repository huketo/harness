/**
 * Synthetic order records for the demo service.
 *
 * Names, cities and amounts are invented for this fixture and do not describe
 * real people, companies or transactions.
 */

import type { Order } from "./orders.ts";

export const ORDERS: readonly Order[] = [
  { id: "ORD-1001", customer: "Rowan Adler", city: "Aldermoor", status: "pending", total: 48.25, created_at: "2026-01-02T06:00:00Z" },
  { id: "ORD-1002", customer: "Mira Dalby", city: "Brightsound", status: "paid", total: 393.25, created_at: "2026-01-03T11:07:00Z" },
  { id: "ORD-1003", customer: "Dario Garrow", city: "Callowfen", status: "shipped", total: 55.75, created_at: "2026-01-04T16:14:00Z" },
  { id: "ORD-1004", customer: "Imani Jarnell", city: "Dunlark", status: "paid", total: 400.75, created_at: "2026-01-05T21:21:00Z" },
  { id: "ORD-1005", customer: "Sela Corvin", city: "Emberhill", status: "cancelled", total: 63.25, created_at: "2026-01-06T09:28:00Z" },
  { id: "ORD-1006", customer: "Tobin Fenwick", city: "Fairloch", status: "pending", total: 408.25, created_at: "2026-01-07T14:35:00Z" },
  { id: "ORD-1007", customer: "Anwen Ivers", city: "Glenmara", status: "paid", total: 70.75, created_at: "2026-01-08T19:42:00Z" },
  { id: "ORD-1008", customer: "Kesh Brant", city: "Hazelrun", status: "shipped", total: 415.75, created_at: "2026-01-09T07:49:00Z" },
  { id: "ORD-1009", customer: "Loris Ester", city: "Aldermoor", status: "pending", total: 78.25, created_at: "2026-01-10T12:56:00Z" },
  { id: "ORD-1010", customer: "Nadia Hollis", city: "Brightsound", status: "paid", total: 423.25, created_at: "2026-01-11T17:03:00Z" },
  { id: "ORD-1011", customer: "Orin Adler", city: "Callowfen", status: "shipped", total: 85.75, created_at: "2026-01-12T22:10:00Z" },
  { id: "ORD-1012", customer: "Pella Dalby", city: "Dunlark", status: "cancelled", total: 430.75, created_at: "2026-01-13T10:17:00Z" },
  { id: "ORD-1013", customer: "Quill Garrow", city: "Emberhill", status: "pending", total: 93.25, created_at: "2026-01-14T15:24:00Z" },
  { id: "ORD-1014", customer: "Rhea Jarnell", city: "Fairloch", status: "paid", total: 438.25, created_at: "2026-01-15T20:31:00Z" },
  { id: "ORD-1015", customer: "Soren Corvin", city: "Glenmara", status: "shipped", total: 100.75, created_at: "2026-01-16T08:38:00Z" },
  { id: "ORD-1016", customer: "Tamsin Fenwick", city: "Hazelrun", status: "paid", total: 445.75, created_at: "2026-01-17T13:45:00Z" },
  { id: "ORD-1017", customer: "Ualen Ivers", city: "Aldermoor", status: "pending", total: 108.25, created_at: "2026-01-18T18:52:00Z" },
  { id: "ORD-1018", customer: "Vesper Brant", city: "Brightsound", status: "cancelled", total: 453.25, created_at: "2026-01-19T06:59:00Z" },
  { id: "ORD-1019", customer: "Wren Ester", city: "Callowfen", status: "shipped", total: 115.75, created_at: "2026-01-20T11:06:00Z" },
  { id: "ORD-1020", customer: "Yara Hollis", city: "Dunlark", status: "paid", total: 460.75, created_at: "2026-01-21T16:13:00Z" },
  { id: "ORD-1021", customer: "Rowan Adler", city: "Emberhill", status: "pending", total: 123.25, created_at: "2026-01-22T21:20:00Z" },
  { id: "ORD-1022", customer: "Mira Dalby", city: "Fairloch", status: "paid", total: 468.25, created_at: "2026-01-23T09:27:00Z" },
  { id: "ORD-1023", customer: "Dario Garrow", city: "Glenmara", status: "shipped", total: 130.75, created_at: "2026-01-24T14:34:00Z" },
  { id: "ORD-1024", customer: "Imani Jarnell", city: "Hazelrun", status: "paid", total: 475.75, created_at: "2026-01-25T19:41:00Z" },
  { id: "ORD-1025", customer: "Sela Corvin", city: "Aldermoor", status: "cancelled", total: 138.25, created_at: "2026-01-26T07:48:00Z" },
  { id: "ORD-1026", customer: "Tobin Fenwick", city: "Brightsound", status: "pending", total: 483.25, created_at: "2026-01-27T12:55:00Z" },
  { id: "ORD-1027", customer: "Anwen Ivers", city: "Callowfen", status: "paid", total: 145.75, created_at: "2026-01-28T17:02:00Z" },
  { id: "ORD-1028", customer: "Kesh Brant", city: "Dunlark", status: "shipped", total: 490.75, created_at: "2026-01-01T22:09:00Z" },
  { id: "ORD-1029", customer: "Loris Ester", city: "Emberhill", status: "pending", total: 153.25, created_at: "2026-01-02T10:16:00Z" },
  { id: "ORD-1030", customer: "Nadia Hollis", city: "Fairloch", status: "paid", total: 70.75, created_at: "2026-01-03T15:23:00Z" },
  { id: "ORD-1031", customer: "Orin Adler", city: "Glenmara", status: "shipped", total: 160.75, created_at: "2026-01-04T20:30:00Z" },
  { id: "ORD-1032", customer: "Pella Dalby", city: "Hazelrun", status: "cancelled", total: 505.75, created_at: "2026-01-05T08:37:00Z" },
  { id: "ORD-1033", customer: "Quill Garrow", city: "Aldermoor", status: "pending", total: 168.25, created_at: "2026-01-06T13:44:00Z" },
  { id: "ORD-1034", customer: "Rhea Jarnell", city: "Brightsound", status: "paid", total: 513.25, created_at: "2026-01-07T18:51:00Z" },
  { id: "ORD-1035", customer: "Soren Corvin", city: "Callowfen", status: "shipped", total: 175.75, created_at: "2026-01-08T06:58:00Z" },
  { id: "ORD-1036", customer: "Tamsin Fenwick", city: "Dunlark", status: "paid", total: 520.75, created_at: "2026-01-09T11:05:00Z" },
  { id: "ORD-1037", customer: "Ualen Ivers", city: "Emberhill", status: "pending", total: 183.25, created_at: "2026-01-10T16:12:00Z" },
  { id: "ORD-1038", customer: "Vesper Brant", city: "Fairloch", status: "cancelled", total: 528.25, created_at: "2026-01-11T21:19:00Z" },
  { id: "ORD-1039", customer: "Wren Ester", city: "Glenmara", status: "shipped", total: 190.75, created_at: "2026-01-12T09:26:00Z" },
  { id: "ORD-1040", customer: "Yara Hollis", city: "Hazelrun", status: "paid", total: 535.75, created_at: "2026-01-13T14:33:00Z" },
];
