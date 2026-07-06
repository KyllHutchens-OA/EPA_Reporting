import pandas as pd
def line_chart_formatting(fig, title_text):
    fig.update_layout(
        title=dict(
            text=f"{title_text} (ML/Month)",
            font=dict(size=50, color='#333333'),
            x=0.5,
            y=0.9,
            xanchor='center',
            yanchor='top'
        ),
        xaxis=dict(
            showgrid=True,
            gridcolor='lightgray',
            tickfont=dict(size=24),
            title='',
            tickformat='%b'
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor='lightgray',
            zeroline=False,
            tickfont=dict(size=24),
            title='',
            rangemode='tozero',  # Use rangemode instead of range
        ),
        legend=dict(
                orientation='h',
                yanchor='top',
                y=-0.15,
                xanchor='center',
                x=0.5,
                font=dict(size=20),  # Increase legend font size
            ),
        showlegend=True,
        
        plot_bgcolor='white',
        margin=dict(l=40, r=40, t=80, b=40),
        width=1800,
        height=900,
        
    )
    return fig
