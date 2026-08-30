document.addEventListener("DOMContentLoaded", async () => {

  /* ============================================================
   * NEXUS ANALYTICS
   * Currency: INR
   * Charts: Chart.js
   * ============================================================ */

  /* ------------------------------------------------------------
   * CURRENCY CONFIGURATION
   * IMPORTANT: Must be initialized BEFORE render() is called.
   * ------------------------------------------------------------ */

  const INR = new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0
  });

  function formatINR(value) {
    if (
      value === null ||
      value === undefined ||
      isNaN(value)
    ) {
      return "₹0";
    }

    return INR.format(Number(value));
  }

  function formatINRShort(value) {
    if (
      value === null ||
      value === undefined ||
      isNaN(value)
    ) {
      return "₹0";
    }

    value = Number(value);

    const absolute = Math.abs(value);

    if (absolute >= 10000000) {
      return "₹" + (value / 10000000).toFixed(2) + "Cr";
    }

    if (absolute >= 100000) {
      return "₹" + (value / 100000).toFixed(2) + "L";
    }

    if (absolute >= 1000) {
      return "₹" + (value / 1000).toFixed(1) + "K";
    }

    return "₹" + Math.round(value);
  }

  function formatNumber(value) {
    if (
      value === null ||
      value === undefined ||
      isNaN(value)
    ) {
      return "0";
    }

    return Number(value).toLocaleString("en-IN");
  }

  function formatPercent(value) {
    if (
      value === null ||
      value === undefined ||
      isNaN(value)
    ) {
      return "0%";
    }

    return Number(value).toFixed(1) + "%";
  }


  /* ============================================================
   * DATASET
   * ============================================================ */

  const datasetId = requireDataset();

  if (!datasetId) {
    return;
  }

  const body = document.getElementById("analytics-body");

  body.innerHTML = loadingBlock(
    "Querying the Gold analytics model…"
  );


  /* ============================================================
   * LOAD ANALYTICS DATA
   * ============================================================ */

  try {

    const { metrics } = await Api.getAnalytics(datasetId);

    render(metrics);

  } catch (err) {

    const message = err?.message || "Unknown error";

    body.innerHTML = errorBlock(
      "Analytics not available yet",
      message.includes("404") ||
      message.toLowerCase().includes("not found")
        ? "Run processing first so Nexus can build the Gold analytics model."
        : message
    );
  }


  /* ============================================================
   * KPI CARD
   * ============================================================ */

  function kpi(label, value) {

    if (value === undefined || value === null) {
      return "";
    }

    return `
      <div class="card kpi">

        <div class="kpi-label">
          ${escapeHtml(label)}
        </div>

        ${
          value.available === false

            ? `
              <div class="kpi-value unavailable">
                Unavailable
              </div>

              <div class="kpi-sub">
                ${escapeHtml(value.reason || "")}
              </div>
            `

            : `
              <div class="kpi-value">
                ${escapeHtml(value.display || "")}
              </div>

              ${
                value.sub
                  ? `
                    <div class="kpi-sub">
                      ${escapeHtml(value.sub)}
                    </div>
                  `
                  : ""
              }
            `
        }

      </div>
    `;
  }


  /* ============================================================
   * CHART CARD
   * ============================================================ */

  function chartCard(title, block, chartId) {

    if (!block || block.available === false) {

      return `
        <div class="card analytics-chart-card">

          <div class="card-title mb-4">
            ${escapeHtml(title)}
          </div>

          <div class="alert alert-info">

            ${escapeHtml(
              block?.reason ||
              "Analytics data is not available."
            )}

          </div>

        </div>
      `;
    }

    return `
      <div class="card analytics-chart-card">

        <div class="card-header">

          <div>

            <div class="card-title">
              ${escapeHtml(title)}
            </div>

            <div class="card-desc">
              Hover over the chart for detailed values
            </div>

          </div>

        </div>

        <div class="analytics-chart-wrapper">

          <canvas id="${chartId}"></canvas>

        </div>

      </div>
    `;
  }


  /* ============================================================
   * RENDER ANALYTICS
   * ============================================================ */

  function render(m) {

    const revenue = m?.revenue_kpis;
    const orders = m?.order_kpis;
    const quantity = m?.quantity_kpis;
    const profitability = m?.profitability;


    /* ------------------------------------------------------------
     * KPI CARDS
     * ------------------------------------------------------------ */

    const kpis = `

      <div class="grid grid-4 mb-6">

        ${kpi(
          "Total Sales",

          revenue?.available === false

            ? revenue

            : {
                display: formatINR(
                  revenue?.total_sales
                )
              }
        )}


        ${kpi(
          "Total Orders",

          orders?.available === false

            ? orders

            : {
                display: formatNumber(
                  orders?.total_orders
                ),

                sub:
                  "Avg order value: " +
                  formatINR(
                    orders?.average_order_value
                  )
              }
        )}


        ${kpi(
          "Total Quantity",

          quantity?.available === false

            ? quantity

            : {
                display: formatNumber(
                  quantity?.total_quantity
                )
              }
        )}


        ${kpi(
          "Profit",

          profitability?.available === false

            ? profitability

            : {
                display: formatINR(
                  profitability?.total_profit
                ),

                sub:
                  profitability?.profit_margin_pct !== null &&
                  profitability?.profit_margin_pct !== undefined

                    ? formatPercent(
                        profitability.profit_margin_pct
                      ) + " margin"

                    : ""
              }
        )}

      </div>
    `;


    /* ------------------------------------------------------------
     * CHART CARDS
     * ------------------------------------------------------------ */

    body.innerHTML = `

      ${kpis}

      <div class="grid grid-2">

        ${chartCard(
          "Sales Trend",
          m?.sales_trend,
          "salesTrendChart"
        )}

        ${chartCard(
          "Sales by Category",
          m?.sales_by_category,
          "categoryChart"
        )}

        ${chartCard(
          "Sales by Region",
          m?.sales_by_region,
          "regionChart"
        )}

        ${chartCard(
          "Top Products",
          m?.top_products,
          "topProductsChart"
        )}

        ${chartCard(
          "Segment Analysis",
          m?.segment_analysis,
          "segmentChart"
        )}

        ${chartCard(
          "Top Customers",
          m?.customer_analysis,
          "customerChart"
        )}

        ${chartCard(
          "Avg Profit by Discount Band",
          m?.discount_analysis,
          "discountChart"
        )}

      </div>
    `;


    /* ------------------------------------------------------------
     * CREATE CHARTS AFTER DOM EXISTS
     * ------------------------------------------------------------ */

    requestAnimationFrame(() => {

      if (
        m?.sales_trend?.available &&
        document.getElementById("salesTrendChart")
      ) {
        createSalesTrendChart(
          m.sales_trend.points || []
        );
      }


      if (
        m?.sales_by_category?.available &&
        document.getElementById("categoryChart")
      ) {
        createCategoryChart(
          m.sales_by_category.categories || []
        );
      }


      if (
        m?.sales_by_region?.available &&
        document.getElementById("regionChart")
      ) {
        createRegionChart(
          m.sales_by_region.regions || []
        );
      }


      if (
        m?.top_products?.available &&
        document.getElementById("topProductsChart")
      ) {
        createTopProductsChart(
          m.top_products.products || []
        );
      }


      if (
        m?.segment_analysis?.available &&
        document.getElementById("segmentChart")
      ) {
        createSegmentChart(
          m.segment_analysis.segments || []
        );
      }


      if (
        m?.customer_analysis?.available &&
        document.getElementById("customerChart")
      ) {
        createCustomerChart(
          m.customer_analysis.top_customers || []
        );
      }


      if (
        m?.discount_analysis?.available &&
        document.getElementById("discountChart")
      ) {
        createDiscountChart(
          m.discount_analysis.bands || []
        );
      }

    });

  }


  /* ============================================================
   * COMMON CHART OPTIONS
   * ============================================================ */

  function commonOptions() {

    return {

      responsive: true,

      maintainAspectRatio: false,


      interaction: {

        mode: "index",

        intersect: false

      },


      animation: {

        duration: 700,

        easing: "easeOutQuart"

      },


      plugins: {

        legend: {

          display: false

        },


        tooltip: {

          enabled: true,

          backgroundColor: "#12172b",

          titleColor: "#ffffff",

          bodyColor: "#ffffff",

          borderColor: "#3452e0",

          borderWidth: 1,

          padding: 12,

          cornerRadius: 8,

          displayColors: false,

          titleFont: {

            size: 13,

            weight: "600"

          },

          bodyFont: {

            size: 13

          }

        }

      },


      scales: {

        x: {

          title: {

            display: true,

            color: "#4b5570",

            font: {

              size: 12,

              weight: "600"

            }

          },

          ticks: {

            color: "#64708a",

            maxRotation: 45,

            minRotation: 0

          },

          grid: {

            display: false

          }

        },


        y: {

          title: {

            display: true,

            text: "Sales (₹)",

            color: "#4b5570",

            font: {

              size: 12,

              weight: "600"

            }

          },

          ticks: {

            color: "#64708a",

            callback: function(value) {

              return formatINRShort(value);

            }

          },

          grid: {

            color: "#e2e5ed"

          },

          beginAtZero: true

        }

      }

    };

  }


  /* ============================================================
   * SALES TREND
   * X = Month
   * Y = Sales (₹)
   * ============================================================ */

  function createSalesTrendChart(points) {

    const canvas =
      document.getElementById(
        "salesTrendChart"
      );

    if (!canvas) return;


    const labels = points.map(
      p =>
        `${p.month}/${String(p.year).slice(2)}`
    );


    const values = points.map(
      p => Number(p.sales || 0)
    );


    new Chart(canvas, {

      type: "line",


      data: {

        labels,


        datasets: [

          {

            label: "Sales",

            data: values,

            borderWidth: 2,

            pointRadius: 4,

            pointHoverRadius: 8,

            tension: 0.35,

            fill: true

          }

        ]

      },


      options: {

        ...commonOptions(),


        scales: {

          ...commonOptions().scales,


          x: {

            ...commonOptions().scales.x,

            title: {

              display: true,

              text: "Month"

            }

          },


          y: {

            ...commonOptions().scales.y,

            title: {

              display: true,

              text: "Sales (₹)"

            }

          }

        },


        plugins: {

          ...commonOptions().plugins,


          tooltip: {

            ...commonOptions().plugins.tooltip,

            callbacks: {

              title: function(context) {

                return "Month: " +
                  context[0].label;

              },


              label: function(context) {

                return "Sales: " +
                  formatINR(
                    context.parsed.y
                  );

              }

            }

          }

        }

      }

    });

  }


  /* ============================================================
   * SALES BY CATEGORY
   * X = Category
   * Y = Sales (₹)
   * ============================================================ */

  function createCategoryChart(categories) {

    const canvas =
      document.getElementById(
        "categoryChart"
      );

    if (!canvas) return;


    const data =
      categories.slice(0, 8);


    new Chart(canvas, {

      type: "bar",


      data: {

        labels: data.map(
          x => x.category
        ),


        datasets: [

          {

            label: "Sales",

            data: data.map(
              x => Number(x.sales || 0)
            ),

            borderWidth: 0,

            borderRadius: 6

          }

        ]

      },


      options: {

        ...commonOptions(),


        scales: {

          ...commonOptions().scales,


          x: {

            ...commonOptions().scales.x,

            title: {

              display: true,

              text: "Category"

            }

          },


          y: {

            ...commonOptions().scales.y,

            title: {

              display: true,

              text: "Sales (₹)"

            }

          }

        },


        plugins: {

          ...commonOptions().plugins,


          tooltip: {

            ...commonOptions().plugins.tooltip,

            callbacks: {

              title: function(context) {

                return "Category: " +
                  context[0].label;

              },


              label: function(context) {

                return "Sales: " +
                  formatINR(
                    context.parsed.y
                  );

              }

            }

          }

        }

      }

    });

  }


  /* ============================================================
   * SALES BY REGION
   * X = Region
   * Y = Sales (₹)
   * ============================================================ */

  function createRegionChart(regions) {

    const canvas =
      document.getElementById(
        "regionChart"
      );

    if (!canvas) return;


    new Chart(canvas, {

      type: "bar",


      data: {

        labels: regions.map(
          x => x.region
        ),


        datasets: [

          {

            label: "Sales",

            data: regions.map(
              x => Number(x.sales || 0)
            ),

            borderWidth: 0,

            borderRadius: 6

          }

        ]

      },


      options: {

        ...commonOptions(),


        scales: {

          ...commonOptions().scales,


          x: {

            ...commonOptions().scales.x,

            title: {

              display: true,

              text: "Region"

            }

          },


          y: {

            ...commonOptions().scales.y,

            title: {

              display: true,

              text: "Sales (₹)"

            }

          }

        },


        plugins: {

          ...commonOptions().plugins,


          tooltip: {

            ...commonOptions().plugins.tooltip,

            callbacks: {

              title: function(context) {

                return "Region: " +
                  context[0].label;

              },


              label: function(context) {

                return "Sales: " +
                  formatINR(
                    context.parsed.y
                  );

              }

            }

          }

        }

      }

    });

  }


  /* ============================================================
   * TOP PRODUCTS
   * X = Sales (₹)
   * Y = Product
   * ============================================================ */

  function createTopProductsChart(products) {

    const canvas =
      document.getElementById(
        "topProductsChart"
      );

    if (!canvas) return;


    const data =
      products.slice(0, 8);


    new Chart(canvas, {

      type: "bar",


      data: {

        labels: data.map(
          x => x.product_name
        ),


        datasets: [

          {

            label: "Sales",

            data: data.map(
              x => Number(x.sales || 0)
            ),

            borderWidth: 0,

            borderRadius: 6

          }

        ]

      },


      options: {

        ...commonOptions(),


        indexAxis: "y",


        scales: {

          x: {

            title: {

              display: true,

              text: "Sales (₹)",

              color: "#4b5570",

              font: {

                size: 12,

                weight: "600"

              }

            },


            ticks: {

              color: "#64708a",

              callback: function(value) {

                return formatINRShort(
                  value
                );

              }

            },


            grid: {

              color: "#e2e5ed"

            },


            beginAtZero: true

          },


          y: {

            title: {

              display: true,

              text: "Product",

              color: "#4b5570",

              font: {

                size: 12,

                weight: "600"

              }

            },


            ticks: {

              color: "#64708a"

            },


            grid: {

              display: false

            }

          }

        },


        plugins: {

          ...commonOptions().plugins,


          tooltip: {

            ...commonOptions().plugins.tooltip,

            callbacks: {

              title: function(context) {

                return "Product: " +
                  context[0].label;

              },


              label: function(context) {

                return "Sales: " +
                  formatINR(
                    context.parsed.x
                  );

              }

            }

          }

        }

      }

    });

  }


  /* ============================================================
   * SEGMENT ANALYSIS
   * X = Customer Segment
   * Y = Sales (₹)
   * ============================================================ */

  function createSegmentChart(segments) {

    const canvas =
      document.getElementById(
        "segmentChart"
      );

    if (!canvas) return;


    new Chart(canvas, {

      type: "bar",


      data: {

        labels: segments.map(
          x => x.segment
        ),


        datasets: [

          {

            label: "Sales",

            data: segments.map(
              x => Number(x.sales || 0)
            ),

            borderWidth: 0,

            borderRadius: 6

          }

        ]

      },


      options: {

        ...commonOptions(),


        scales: {

          ...commonOptions().scales,


          x: {

            ...commonOptions().scales.x,

            title: {

              display: true,

              text: "Customer Segment"

            }

          },


          y: {

            ...commonOptions().scales.y,

            title: {

              display: true,

              text: "Sales (₹)"

            }

          }

        },


        plugins: {

          ...commonOptions().plugins,


          tooltip: {

            ...commonOptions().plugins.tooltip,

            callbacks: {

              title: function(context) {

                return "Segment: " +
                  context[0].label;

              },


              label: function(context) {

                return "Sales: " +
                  formatINR(
                    context.parsed.y
                  );

              }

            }

          }

        }

      }

    });

  }


  /* ============================================================
   * TOP CUSTOMERS
   * X = Sales (₹)
   * Y = Customer
   * ============================================================ */

  function createCustomerChart(customers) {

    const canvas =
      document.getElementById(
        "customerChart"
      );

    if (!canvas) return;


    const data =
      customers.slice(0, 8);


    new Chart(canvas, {

      type: "bar",


      data: {

        labels: data.map(
          x => x.customer_name
        ),


        datasets: [

          {

            label: "Sales",

            data: data.map(
              x => Number(x.sales || 0)
            ),

            borderWidth: 0,

            borderRadius: 6

          }

        ]

      },


      options: {

        ...commonOptions(),


        indexAxis: "y",


        scales: {

          x: {

            title: {

              display: true,

              text: "Sales (₹)",

              color: "#4b5570",

              font: {

                size: 12,

                weight: "600"

              }

            },


            ticks: {

              color: "#64708a",

              callback: function(value) {

                return formatINRShort(
                  value
                );

              }

            },


            grid: {

              color: "#e2e5ed"

            },


            beginAtZero: true

          },


          y: {

            title: {

              display: true,

              text: "Customer",

              color: "#4b5570",

              font: {

                size: 12,

                weight: "600"

              }

            },


            ticks: {

              color: "#64708a"

            },


            grid: {

              display: false

            }

          }

        },


        plugins: {

          ...commonOptions().plugins,


          tooltip: {

            ...commonOptions().plugins.tooltip,

            callbacks: {

              title: function(context) {

                return "Customer: " +
                  context[0].label;

              },


              label: function(context) {

                return "Sales: " +
                  formatINR(
                    context.parsed.x
                  );

              }

            }

          }

        }

      }

    });

  }


  /* ============================================================
   * DISCOUNT ANALYSIS
   * X = Discount Band
   * Y = Average Profit (₹)
   * ============================================================ */

  function createDiscountChart(bands) {

    const canvas =
      document.getElementById(
        "discountChart"
      );

    if (!canvas) return;


    new Chart(canvas, {

      type: "bar",


      data: {

        labels: bands.map(
          x => x.discount_band
        ),


        datasets: [

          {

            label: "Average Profit",

            data: bands.map(
              x =>
                Number(
                  x.avg_profit || 0
                )
            ),

            borderWidth: 0,

            borderRadius: 6

          }

        ]

      },


      options: {

        ...commonOptions(),


        scales: {

          ...commonOptions().scales,


          x: {

            ...commonOptions().scales.x,

            title: {

              display: true,

              text: "Discount Band"

            }

          },


          y: {

            ...commonOptions().scales.y,

            title: {

              display: true,

              text: "Average Profit (₹)"

            },


            ticks: {

              color: "#64708a",

              callback: function(value) {

                return formatINRShort(
                  value
                );

              }

            }

          }

        },


        plugins: {

          ...commonOptions().plugins,


          tooltip: {

            ...commonOptions().plugins.tooltip,

            callbacks: {

              title: function(context) {

                return "Discount Band: " +
                  context[0].label;

              },


              label: function(context) {

                return "Average Profit: " +
                  formatINR(
                    context.parsed.y
                  );

              }

            }

          }

        }

      }

    });

  }

});